from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import logging
from models import Appointment, AppointmentCreate, AppointmentUpdate, AppointmentStatus, Patient, Doctor
from database import db
from calendar_service import calendar_service
from reminder_service import send_whatsapp_reminder
from utils import sanitize_input

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("appointment")

class AppointmentService:
    @staticmethod
    async def schedule_appointment(appointment_data: AppointmentCreate) -> Optional[Appointment]:
        """
        Schedule a new appointment and create a corresponding calendar event.
        """
        try:
            # Check if the doctor exists
            doctor = await db.get_doctor(appointment_data.doctor_id)
            if not doctor:
                logger.error(f"Doctor {appointment_data.doctor_id} not found")
                return None
            
            # Check if the patient exists
            patient = await db.get_patient(appointment_data.patient_id)
            if not patient:
                logger.error(f"Patient {appointment_data.patient_id} not found")
                return None
            
            # Sanitize user input
            appointment_data.reason = sanitize_input(appointment_data.reason) if appointment_data.reason else None
            # Check for scheduling conflicts
            if await AppointmentService._has_scheduling_conflict(appointment_data):
                logger.warning("Scheduling conflict detected")
                return None
            
            # Create the appointment in the database
            appointment = await db.create_appointment(appointment_data)
            
            # Create calendar event
            calendar_event = await calendar_service.create_calendar_event(appointment)
            
            # Update appointment with calendar event ID
            if calendar_event:
                appointment.metadata = appointment.metadata or {}
                appointment.metadata['calendar_event_id'] = calendar_event['id']
                appointment = await db.update_appointment(
                    appointment.id,
                    AppointmentUpdate(metadata=appointment.metadata)
                )
            
            # Send WhatsApp reminder with retry logic
            reminder_sent = False
            for attempt in range(2):  # Try twice
                try:
                    reminder_sent = send_whatsapp_reminder(
                        to_number=patient.phone_number,
                        appointment_time=appointment.scheduled_time,
                        patient_name=patient.full_name or "Patient",
                        doctor_name=doctor.name if doctor else None
                    )
                    if reminder_sent:
                        break
                except Exception as e:
                    logger.error(f"Failed to send WhatsApp reminder (attempt {attempt+1}): {e}")
            if not reminder_sent:
                logger.warning(f"WhatsApp reminder could not be sent to {patient.phone_number}")
                # Optionally, add a warning to the appointment metadata
                appointment.metadata['reminder_warning'] = 'WhatsApp reminder failed'
                await db.update_appointment(
                    appointment.id,
                    AppointmentUpdate(metadata=appointment.metadata)
                )
            
            logger.info(f"Successfully scheduled appointment {appointment.id}")
            return appointment
            
        except Exception as e:
            logger.error(f"Error scheduling appointment: {str(e)}")
            return None
    
    @staticmethod
    async def reschedule_appointment(
        appointment_id: str, 
        new_time: datetime,
        new_doctor_id: Optional[str] = None
    ) -> Optional[Appointment]:
        """
        Reschedule an existing appointment to a new time and optionally with a different doctor.
        """
        try:
            # Get the existing appointment
            appointment = await db.get_appointment(appointment_id)
            if not appointment:
                logger.error(f"Appointment {appointment_id} not found")
                return None
            
            if appointment.status != AppointmentStatus.SCHEDULED:
                logger.error(f"Cannot reschedule appointment in status: {appointment.status}")
                return None
            
            # Prepare update data
            update_data = {
                'scheduled_time': new_time,
                'status': AppointmentStatus.SCHEDULED
            }
            
            if new_doctor_id and new_doctor_id != appointment.doctor_id:
                # Verify new doctor exists
                new_doctor = await db.get_doctor(new_doctor_id)
                if not new_doctor:
                    logger.error(f"New doctor {new_doctor_id} not found")
                    return None
                update_data['doctor_id'] = new_doctor_id
            
            # Check for scheduling conflicts with the new time
            conflict_check = AppointmentCreate(
                patient_id=appointment.patient_id,
                doctor_id=new_doctor_id or appointment.doctor_id,
                scheduled_time=new_time,
                duration_minutes=appointment.duration_minutes
            )
            
            if await AppointmentService._has_scheduling_conflict(conflict_check, exclude_appointment_id=appointment_id):
                logger.warning("Scheduling conflict detected for reschedule")
                return None
            
            # Update the appointment
            updated_appointment = await db.update_appointment(
                appointment_id,
                AppointmentUpdate(**update_data)
            )
            
            if not updated_appointment:
                logger.error(f"Failed to update appointment {appointment_id}")
                return None
            
            # Update the calendar event
            await calendar_service.update_calendar_event(updated_appointment)
            
            logger.info(f"Successfully rescheduled appointment {appointment_id}")
            return updated_appointment
            
        except Exception as e:
            logger.error(f"Error rescheduling appointment: {str(e)}")
            return None
    
    @staticmethod
    async def cancel_appointment(appointment_id: str, reason: Optional[str] = None) -> bool:
        """
        Cancel an appointment and update the calendar event.
        """
        try:
            # Get the appointment
            appointment = await db.get_appointment(appointment_id)
            if not appointment:
                logger.error(f"Appointment {appointment_id} not found")
                return False
            
            # Only allow cancelling scheduled appointments
            if appointment.status != AppointmentStatus.SCHEDULED:
                logger.warning(f"Cannot cancel appointment in status: {appointment.status}")
                return False
            
            # Update the appointment status
            update_data = {
                'status': AppointmentStatus.CANCELLED,
                'notes': f"{appointment.notes or ''}\nCancelled: {reason or 'No reason provided'}".strip()
            }
            
            updated = await db.update_appointment(
                appointment_id,
                AppointmentUpdate(**update_data)
            )
            
            if not updated:
                logger.error(f"Failed to cancel appointment {appointment_id}")
                return False
            
            # Update the calendar event
            await calendar_service.update_calendar_event(updated)
            
            logger.info(f"Successfully cancelled appointment {appointment_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling appointment: {str(e)}")
            return False
    
    @staticmethod
    async def complete_appointment(appointment_id: str, notes: Optional[str] = None) -> bool:
        """
        Mark an appointment as completed.
        """
        try:
            # Get the appointment
            appointment = await db.get_appointment(appointment_id)
            if not appointment:
                logger.error(f"Appointment {appointment_id} not found")
                return False
            
            # Only allow completing scheduled appointments
            if appointment.status != AppointmentStatus.SCHEDULED:
                logger.warning(f"Cannot complete appointment in status: {appointment.status}")
                return False
            
            # Update the appointment status
            update_data = {
                'status': AppointmentStatus.COMPLETED,
                'notes': f"{appointment.notes or ''}\nCompleted: {notes or 'No notes provided'}".strip()
            }
            
            updated = await db.update_appointment(
                appointment_id,
                AppointmentUpdate(**update_data)
            )
            
            if not updated:
                logger.error(f"Failed to mark appointment {appointment_id} as completed")
                return False
            
            # Update the calendar event
            await calendar_service.update_calendar_event(updated)
            
            logger.info(f"Successfully marked appointment {appointment_id} as completed")
            return True
            
        except Exception as e:
            logger.error(f"Error completing appointment: {str(e)}")
            return False
    
    @staticmethod
    async def get_available_slots(
        doctor_id: str,
        date: datetime,
        duration_minutes: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get available time slots for a doctor on a specific date.
        """
        try:
            # Get doctor's working hours
            doctor = await db.get_doctor(doctor_id)
            if not doctor:
                logger.error(f"Doctor {doctor_id} not found")
                return []
            
            # Get the day of week (0=Monday, 6=Sunday)
            weekday = date.weekday()
            weekdays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
            day_name = weekdays[weekday].lower()
            
            # Get working hours for this day
            working_hours = doctor.working_hours.get(day_name, [])
            if not working_hours:
                logger.info(f"Doctor {doctor_id} does not work on {day_name}")
                return []
            
            # Get existing appointments for this doctor on this day
            start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = start_of_day + timedelta(days=1)
            
            # Get all appointments for this doctor on this day
            # Note: This is a simplified example - in a real app, you'd use a proper query
            all_appointments = await db.get_doctor_appointments(
                doctor_id=doctor_id,
                start_date=start_of_day,
                end_date=end_of_day
            )
            
            # Generate available slots
            available_slots = []
            
            for time_range in working_hours:
                current_time = datetime.combine(date.date(), time_range['start'])
                end_time = datetime.combine(date.date(), time_range['end'])
                
                while current_time + timedelta(minutes=duration_minutes) <= end_time:
                    slot_end = current_time + timedelta(minutes=duration_minutes)
                    
                    # Check if this slot is available
                    is_available = True
                    for appt in all_appointments:
                        appt_start = appt.scheduled_time
                        appt_end = appt_start + timedelta(minutes=appt.duration_minutes)
                        
                        # Check for overlap
                        if (current_time < appt_end and slot_end > appt_start):
                            is_available = False
                            current_time = appt_end  # Skip past this appointment
                            break
                    
                    if is_available:
                        available_slots.append({
                            'start': current_time,
                            'end': slot_end,
                            'duration_minutes': duration_minutes
                        })
                        current_time += timedelta(minutes=15)  # Next slot starts 15 minutes later
                    
                    if not is_available:
                        continue  # Already moved current_time past the conflicting appointment
            
            return available_slots
            
        except Exception as e:
            logger.error(f"Error getting available slots: {str(e)}")
            return []
    
    @staticmethod
    async def _has_scheduling_conflict(
        appointment: AppointmentCreate,
        exclude_appointment_id: Optional[str] = None
    ) -> bool:
        """
        Check if scheduling this appointment would cause a conflict.
        """
        try:
            # Get all appointments for this doctor around this time
            start_time = appointment.scheduled_time - timedelta(minutes=30)
            end_time = appointment.scheduled_time + timedelta(minutes=appointment.duration_minutes + 30)
            
            # Get conflicting appointments
            # Note: This is a simplified example - in a real app, you'd use a proper query
            appointments = await db.get_doctor_appointments(
                doctor_id=appointment.doctor_id,
                start_date=start_time,
                end_date=end_time,
                exclude_appointment_id=exclude_appointment_id
            )
            
            # Check for overlap with each existing appointment
            for existing_appt in appointments:
                existing_start = existing_appt.scheduled_time
                existing_end = existing_start + timedelta(minutes=existing_appt.duration_minutes)
                
                new_start = appointment.scheduled_time
                new_end = new_start + timedelta(minutes=appointment.duration_minutes)
                
                if new_start < existing_end and new_end > existing_start:
                    return True  # Conflict found
            
            return False  # No conflicts
            
        except Exception as e:
            logger.error(f"Error checking scheduling conflict: {str(e)}")
            return True  # Assume conflict on error to be safe

# Initialize appointment service
appointment_service = AppointmentService()
