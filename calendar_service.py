import os
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import pickle
import logging
from models import Appointment, AppointmentStatus, Doctor
from database import db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("calendar")

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/calendar']
TOKEN_FILE = 'token.pickle'
CREDENTIALS_FILE = 'credentials.json'

class CalendarService:
    def __init__(self):
        self.creds = self._get_credentials()
        self.service = build('calendar', 'v3', credentials=self.creds)
    
    def _get_credentials(self):
        """Get valid user credentials from storage or run the OAuth flow."""
        creds = None
        
        # The file token.pickle stores the user's access and refresh tokens
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, 'rb') as token:
                creds = pickle.load(token)
        
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(CREDENTIALS_FILE):
                    raise FileNotFoundError(
                        f"Credentials file '{CREDENTIALS_FILE}' not found. "
                        "Please download it from Google Cloud Console."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Save the credentials for the next run
            with open(TOKEN_FILE, 'wb') as token:
                pickle.dump(creds, token)
        
        return creds
    
    async def create_calendar_event(self, appointment: Appointment) -> Optional[Dict[str, Any]]:
        """Create a calendar event for an appointment."""
        try:
            # Get doctor's calendar ID
            doctor = await db.get_doctor(appointment.doctor_id)
            if not doctor or not doctor.calendar_id:
                logger.error(f"Doctor {appointment.doctor_id} not found or has no calendar ID")
                return None
            
            # Get patient details
            patient = await db.get_patient(appointment.patient_id)
            if not patient:
                logger.error(f"Patient {appointment.patient_id} not found")
                return None
            
            # Format start and end times
            start_time = appointment.scheduled_time.isoformat()
            end_time = (appointment.scheduled_time + timedelta(minutes=appointment.duration_minutes)).isoformat()
            
            # Create event
            event = {
                'summary': f'Appointment with {patient.full_name or "Patient"}',
                'description': f'Appointment ID: {appointment.id}\n'
                             f'Reason: {appointment.reason or "Not specified"}\n'
                             f'Notes: {appointment.notes or ""}',
                'start': {
                    'dateTime': start_time,
                    'timeZone': 'UTC',
                },
                'end': {
                    'dateTime': end_time,
                    'timeZone': 'UTC',
                },
                'attendees': [
                    {'email': patient.email} if patient.email else None,
                    {'email': doctor.email} if hasattr(doctor, 'email') and doctor.email else None,
                ],
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'email', 'minutes': 24 * 60},  # 1 day before
                        {'method': 'popup', 'minutes': 30},       # 30 min before
                    ],
                },
                'guestsCanModify': False,
                'guestsCanInviteOthers': False,
                'guestsCanSeeOtherGuests': False,
                'transparency': 'opaque',
                'visibility': 'private',
            }
            
            # Remove None values from attendees
            event['attendees'] = [a for a in event['attendees'] if a is not None]
            
            # Create the event
            created_event = self.service.events().insert(
                calendarId=doctor.calendar_id,
                body=event,
                sendUpdates='all',
            ).execute()
            
            logger.info(f"Created calendar event {created_event['id']} for appointment {appointment.id}")
            return created_event
            
        except HttpError as error:
            logger.error(f"An error occurred while creating calendar event: {error}")
            return None
    
    async def update_calendar_event(self, appointment: Appointment) -> Optional[Dict[str, Any]]:
        """Update an existing calendar event for an appointment."""
        try:
            if not appointment.metadata or 'calendar_event_id' not in appointment.metadata:
                logger.warning(f"Appointment {appointment.id} has no associated calendar event")
                return await self.create_calendar_event(appointment)
            
            doctor = await db.get_doctor(appointment.doctor_id)
            if not doctor or not doctor.calendar_id:
                logger.error(f"Doctor {appointment.doctor_id} not found or has no calendar ID")
                return None
            
            # Get the existing event
            event = self.service.events().get(
                calendarId=doctor.calendar_id,
                eventId=appointment.metadata['calendar_event_id']
            ).execute()
            
            # Update event details
            event['status'] = 'confirmed' if appointment.status == 'scheduled' else appointment.status
            
            if appointment.status == 'cancelled':
                event['status'] = 'cancelled'
            
            # Update times if they've changed
            event['start']['dateTime'] = appointment.scheduled_time.isoformat()
            event['end']['dateTime'] = (
                appointment.scheduled_time + timedelta(minutes=appointment.duration_minutes)
            ).isoformat()
            
            # Update the event
            updated_event = self.service.events().update(
                calendarId=doctor.calendar_id,
                eventId=appointment.metadata['calendar_event_id'],
                body=event,
                sendUpdates='all',
            ).execute()
            
            logger.info(f"Updated calendar event {updated_event['id']} for appointment {appointment.id}")
            return updated_event
            
        except HttpError as error:
            if error.resp.status == 404:  # Event not found
                logger.warning(f"Calendar event not found, creating new one for appointment {appointment.id}")
                return await self.create_calendar_event(appointment)
            logger.error(f"An error occurred while updating calendar event: {error}")
            return None
    
    async def delete_calendar_event(self, appointment: Appointment) -> bool:
        """Delete a calendar event for an appointment."""
        try:
            if not appointment.metadata or 'calendar_event_id' not in appointment.metadata:
                logger.warning(f"Appointment {appointment.id} has no associated calendar event to delete")
                return False
            
            doctor = await db.get_doctor(appointment.doctor_id)
            if not doctor or not doctor.calendar_id:
                logger.error(f"Doctor {appointment.doctor_id} not found or has no calendar ID")
                return False
            
            self.service.events().delete(
                calendarId=doctor.calendar_id,
                eventId=appointment.metadata['calendar_event_id'],
                sendUpdates='all',
            ).execute()
            
            logger.info(f"Deleted calendar event for appointment {appointment.id}")
            return True
            
        except HttpError as error:
            if error.resp.status == 410:  # Already deleted
                logger.warning(f"Calendar event already deleted for appointment {appointment.id}")
                return True
            logger.error(f"An error occurred while deleting calendar event: {error}")
            return False

# Initialize calendar service
calendar_service = CalendarService()
