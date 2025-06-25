from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, EmailStr, validator
from enum import Enum
from datetime import time

class PatientStatus(str, Enum):
    NEW = "new"
    ACTIVE = "active"
    INACTIVE = "inactive"

class AppointmentStatus(str, Enum):
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"n
class PatientBase(BaseModel):
    phone_number: str = Field(..., description="Patient's primary phone number")
    full_name: Optional[str] = Field(None, description="Patient's full name")
    email: Optional[EmailStr] = Field(None, description="Patient's email address")
    date_of_birth: Optional[str] = Field(None, description="Patient's date of birth (YYYY-MM-DD)")
    status: PatientStatus = Field(default=PatientStatus.NEW, description="Patient status")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional patient information")
    last_interaction: Optional[datetime] = Field(None, description="Last interaction timestamp")
    
    @validator('phone_number')
    def validate_phone_number(cls, v):
        # Basic phone number validation (can be enhanced)
        if not v.startswith('+'):
            raise ValueError('Phone number must include country code (e.g., +1...)')
        return v

class PatientCreate(PatientBase):
    pass

class PatientUpdate(PatientBase):
    phone_number: Optional[str] = None
    
class Patient(PatientBase):
    id: str = Field(..., description="Unique patient identifier")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        from_attributes = True

class AppointmentBase(BaseModel):
    patient_id: str = Field(..., description="ID of the patient")
    doctor_id: str = Field(..., description="ID of the doctor")
    scheduled_time: datetime = Field(..., description="Scheduled appointment time")
    duration_minutes: int = Field(30, description="Duration of the appointment in minutes")
    status: AppointmentStatus = Field(AppointmentStatus.SCHEDULED, description="Appointment status")
    reason: Optional[str] = Field(None, description="Reason for the appointment")
    notes: Optional[str] = Field(None, description="Additional notes")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional appointment data")

class AppointmentCreate(AppointmentBase):
    pass

class AppointmentUpdate(BaseModel):
    scheduled_time: Optional[datetime] = None
    status: Optional[AppointmentStatus] = None
    reason: Optional[str] = None
    notes: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class Appointment(AppointmentBase):
    id: str = Field(..., description="Unique appointment identifier")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        from_attributes = True

class Doctor(BaseModel):
    id: str = Field(..., description="Unique doctor identifier")
    name: str = Field(..., description="Doctor's full name")
    specialty: Optional[str] = Field(None, description="Doctor's specialty")
    working_hours: Dict[str, List[Dict[str, time]]] = Field(
        default_factory=dict, 
        description="Working hours by weekday, e.g., {'monday': [{'start': '09:00', 'end': '17:00'}]}"
    )
    calendar_id: Optional[str] = Field(None, description="Google Calendar ID for the doctor")
