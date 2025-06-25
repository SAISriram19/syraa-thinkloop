import os
from plivo import RestClient
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("reminder_service")

PLIVO_AUTH_ID = os.getenv("PLIVO_AUTH_ID")
PLIVO_AUTH_TOKEN = os.getenv("PLIVO_AUTH_TOKEN")
PLIVO_WHATSAPP_NUMBER = os.getenv("PLIVO_PHONE_NUMBER")  # Your Plivo WhatsApp-enabled number

client = RestClient(auth_id=PLIVO_AUTH_ID, auth_token=PLIVO_AUTH_TOKEN)

def send_whatsapp_reminder(to_number: str, appointment_time: datetime, patient_name: str, doctor_name: str = None):
    """
    Send a WhatsApp reminder for an appointment using Plivo. Returns True if sent, False otherwise.
    """
    if not (PLIVO_AUTH_ID and PLIVO_AUTH_TOKEN and PLIVO_WHATSAPP_NUMBER):
        logger.error("Plivo credentials or WhatsApp number not set in environment variables.")
        return False
    # Format the message
    time_str = appointment_time.strftime('%A, %d %B %Y at %I:%M %p')
    doctor_part = f" with Dr. {doctor_name}" if doctor_name else ""
    message = (
        f"Hello {patient_name}, this is a reminder for your upcoming appointment{doctor_part} "
        f"on {time_str}. If you need to reschedule or cancel, please reply to this message."
    )
    for attempt in range(2):
        try:
            response = client.messages.create(
                src=f"whatsapp:{PLIVO_WHATSAPP_NUMBER}",
                dst=f"whatsapp:{to_number}",
                text=message
            )
            logger.info(f"WhatsApp reminder sent to {to_number}: {response.message_uuid}")
            return True
        except Exception as e:
            logger.error(f"Failed to send WhatsApp reminder to {to_number} (attempt {attempt+1}): {e}")
    return False 