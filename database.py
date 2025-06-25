import os
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from supabase import create_client, Client as SupabaseClient
from dotenv import load_dotenv
import logging
from models import Patient, PatientCreate, PatientUpdate, Appointment, AppointmentCreate, AppointmentUpdate, Doctor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("database")

# Load environment variables
load_dotenv()

class DatabaseService:
    def __init__(self):
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_KEY")
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("Missing Supabase URL or key in environment variables")
            
        self.supabase: SupabaseClient = create_client(self.supabase_url, self.supabase_key)
        logger.info("Initialized Supabase client")
    
    # Patient CRUD Operations
    async def create_patient(self, patient: PatientCreate) -> Patient:
        """Create a new patient record."""
        try:
            result = self.supabase.table("patients").insert(patient.dict()).execute()
            return Patient(**result.data[0])
        except Exception as e:
            logger.error(f"Error creating patient: {str(e)}")
            raise
    
    async def get_patient(self, patient_id: str) -> Optional[Patient]:
        """Retrieve a patient by ID."""
        try:
            result = self.supabase.table("patients").select("*").eq("id", patient_id).execute()
            return Patient(**result.data[0]) if result.data else None
        except Exception as e:
            logger.error(f"Error getting patient {patient_id}: {str(e)}")
            return None
    
    async def find_patient_by_phone(self, phone_number: str) -> Optional[Patient]:
        """Find a patient by phone number."""
        try:
            result = self.supabase.table("patients").select("*").eq("phone_number", phone_number).execute()
            return Patient(**result.data[0]) if result.data else None
        except Exception as e:
            logger.error(f"Error finding patient by phone {phone_number}: {str(e)}")
            return None
    
    async def update_patient(self, patient_id: str, patient_update: PatientUpdate) -> Optional[Patient]:
        """Update a patient's information."""
        try:
            update_data = patient_update.dict(exclude_unset=True)
            update_data['updated_at'] = datetime.utcnow().isoformat()
            
            result = self.supabase.table("patients")\
                .update(update_data)\
                .eq("id", patient_id)\
                .execute()
                
            return Patient(**result.data[0]) if result.data else None
        except Exception as e:
            logger.error(f"Error updating patient {patient_id}: {str(e)}")
            return None
    
    # Appointment CRUD Operations
    async def create_appointment(self, appointment: AppointmentCreate) -> Appointment:
        """Create a new appointment."""
        try:
            result = self.supabase.table("appointments").insert(appointment.dict()).execute()
            return Appointment(**result.data[0])
        except Exception as e:
            logger.error(f"Error creating appointment: {str(e)}")
            raise
    
    async def get_appointment(self, appointment_id: str) -> Optional[Appointment]:
        """Retrieve an appointment by ID."""
        try:
            result = self.supabase.table("appointments").select("*").eq("id", appointment_id).execute()
            return Appointment(**result.data[0]) if result.data else None
        except Exception as e:
            logger.error(f"Error getting appointment {appointment_id}: {str(e)}")
            return None
    
    async def get_patient_appointments(self, patient_id: str, limit: int = 10, upcoming: bool = True) -> List[Appointment]:
        """Get a patient's appointments, optionally filtered by upcoming/past."""
        try:
            query = self.supabase.table("appointments").select("*").eq("patient_id", patient_id)
            
            if upcoming:
                query = query.gte("scheduled_time", datetime.utcnow().isoformat())
            else:
                query = query.lt("scheduled_time", datetime.utcnow().isoformat())
                
            query = query.order("scheduled_time", desc=not upcoming).limit(limit)
            result = query.execute()
            
            return [Appointment(**appt) for appt in result.data]
        except Exception as e:
            logger.error(f"Error getting appointments for patient {patient_id}: {str(e)}")
            return []
    
    async def update_appointment(self, appointment_id: str, update: AppointmentUpdate) -> Optional[Appointment]:
        """Update an appointment."""
        try:
            update_data = update.dict(exclude_unset=True)
            update_data['updated_at'] = datetime.utcnow().isoformat()
            
            result = self.supabase.table("appointments")\
                .update(update_data)\
                .eq("id", appointment_id)\
                .execute()
                
            return Appointment(**result.data[0]) if result.data else None
        except Exception as e:
            logger.error(f"Error updating appointment {appointment_id}: {str(e)}")
            return None
    
    async def cancel_appointment(self, appointment_id: str) -> bool:
        """Cancel an appointment."""
        try:
            from models import AppointmentStatus
            
            result = self.supabase.table("appointments")\
                .update({
                    'status': AppointmentStatus.CANCELLED,
                    'updated_at': datetime.utcnow().isoformat()
                })\
                .eq("id", appointment_id)\
                .execute()
                
            return len(result.data) > 0
        except Exception as e:
            logger.error(f"Error cancelling appointment {appointment_id}: {str(e)}")
            return False
    
    # Doctor Operations
    async def get_doctor(self, doctor_id: str) -> Optional[Doctor]:
        """Retrieve a doctor by ID."""
        try:
            result = self.supabase.table("doctors").select("*").eq("id", doctor_id).execute()
            return Doctor(**result.data[0]) if result.data else None
        except Exception as e:
            logger.error(f"Error getting doctor {doctor_id}: {str(e)}")
            return None

# Initialize database service
db = DatabaseService()
