from typing import List, Optional, Dict, Any
import logging
from models import Patient, PatientCreate, PatientUpdate, PatientStatus, Appointment
from database import db
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("patient")

class PatientService:
    @staticmethod
    async def create_patient(patient_data: PatientCreate) -> Optional[Patient]:
        """
        Create a new patient record.
        """
        try:
            # Check if patient with this phone number already exists
            existing_patient = await db.find_patient_by_phone(patient_data.phone_number)
            if existing_patient:
                logger.warning(f"Patient with phone {patient_data.phone_number} already exists")
                return existing_patient
            
            # Set status to ACTIVE for new patients
            patient_data.status = PatientStatus.ACTIVE
            
            # Create the patient
            patient = await db.create_patient(patient_data)
            
            logger.info(f"Created new patient {patient.id}")
            return patient
            
        except Exception as e:
            logger.error(f"Error creating patient: {str(e)}")
            return None
    
    @staticmethod
    async def update_patient(
        patient_id: str, 
        update_data: PatientUpdate
    ) -> Optional[Patient]:
        """
        Update a patient's information.
        """
        try:
            # Get the existing patient
            patient = await db.get_patient(patient_id)
            if not patient:
                logger.error(f"Patient {patient_id} not found")
                return None
            
            # Update the patient
            updated_patient = await db.update_patient(patient_id, update_data)
            
            if not updated_patient:
                logger.error(f"Failed to update patient {patient_id}")
                return None
            
            logger.info(f"Updated patient {patient_id}")
            return updated_patient
            
        except Exception as e:
            logger.error(f"Error updating patient: {str(e)}")
            return None
    
    @staticmethod
    async def get_patient(patient_id: str) -> Optional[Patient]:
        """
        Get a patient by ID.
        """
        try:
            return await db.get_patient(patient_id)
        except Exception as e:
            logger.error(f"Error getting patient {patient_id}: {str(e)}")
            return None
    
    @staticmethod
    async def find_patient_by_phone(phone_number: str) -> Optional[Patient]:
        """
        Find a patient by phone number.
        """
        try:
            return await db.find_patient_by_phone(phone_number)
        except Exception as e:
            logger.error(f"Error finding patient by phone {phone_number}: {str(e)}")
            return None
    
    @staticmethod
    async def get_patient_appointments(
        patient_id: str, 
        upcoming: bool = True,
        limit: int = 10
    ) -> List[Appointment]:
        """
        Get a patient's appointments, optionally filtered by upcoming/past.
        """
        try:
            return await db.get_patient_appointments(patient_id, limit=limit, upcoming=upcoming)
        except Exception as e:
            logger.error(f"Error getting appointments for patient {patient_id}: {str(e)}")
            return []
    
    @staticmethod
    async def get_patient_history(patient_id: str, days: int = 30) -> Dict[str, Any]:
        """
        Get a patient's appointment history and other relevant information.
        """
        try:
            # Get the patient
            patient = await db.get_patient(patient_id)
            if not patient:
                logger.error(f"Patient {patient_id} not found")
                return {}
            
            # Get recent appointments
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            # Get all appointments in this date range
            # Note: This is a simplified example - in a real app, you'd use a proper query
            all_appointments = await db.get_patient_appointments(patient_id, limit=100)  # Adjust limit as needed
            
            # Filter by date range
            recent_appointments = [
                appt for appt in all_appointments 
                if start_date <= appt.scheduled_time <= end_date
            ]
            
            # Count appointments by status
            status_counts = {}
            for appt in all_appointments:
                status = appt.status.value if hasattr(appt.status, 'value') else appt.status
                status_counts[status] = status_counts.get(status, 0) + 1
            
            # Calculate no-show rate
            total_appointments = len(all_appointments)
            no_show_count = len([a for a in all_appointments if a.status == "no_show"])
            no_show_rate = (no_show_count / total_appointments * 100) if total_appointments > 0 else 0
            
            return {
                'patient': patient,
                'recent_appointments': recent_appointments,
                'appointment_stats': {
                    'total': total_appointments,
                    'status_counts': status_counts,
                    'no_show_rate': round(no_show_rate, 2),
                },
                'summary': {
                    'last_visit': max(a.scheduled_time for a in all_appointments) if all_appointments else None,
                    'next_appointment': next(
                        (a for a in all_appointments 
                         if a.status == "scheduled" and a.scheduled_time >= datetime.utcnow()),
                        None
                    ),
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting patient history: {str(e)}")
            return {}
    
    @staticmethod
    async def merge_patients(primary_patient_id: str, duplicate_patient_id: str) -> bool:
        """
        Merge two patient records, keeping the primary record and transferring all data.
        """
        try:
            # Get both patients
            primary = await db.get_patient(primary_patient_id)
            duplicate = await db.get_patient(duplicate_patient_id)
            
            if not primary or not duplicate:
                logger.error("One or both patients not found")
                return False
            
            # Merge fields (keep non-null values from duplicate if primary is null)
            update_data = {}
            for field in PatientUpdate.__annotations__:
                if field == 'id':
                    continue
                    
                primary_val = getattr(primary, field, None)
                duplicate_val = getattr(duplicate, field, None)
                
                if not primary_val and duplicate_val:
                    update_data[field] = duplicate_val
            
            # Merge metadata
            if duplicate.metadata:
                update_data['metadata'] = {**duplicate.metadata, **(primary.metadata or {})}
            
            # Update the primary patient
            await db.update_patient(primary_patient_id, PatientUpdate(**update_data))
            
            # Update all appointments for the duplicate patient
            # Note: In a real app, you'd update all references in other tables
            
            # Mark the duplicate as inactive
            await db.update_patient(
                duplicate_patient_id, 
                PatientUpdate(status=PatientStatus.INACTIVE, metadata={"merged_into": primary_patient_id})
            )
            
            logger.info(f"Merged patient {duplicate_patient_id} into {primary_patient_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error merging patients: {str(e)}")
            return False

# Initialize patient service
patient_service = PatientService()
