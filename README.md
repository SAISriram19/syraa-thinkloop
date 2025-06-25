# SYRAA – AI Receptionist for Clinics & Hospitals

**SYRAA** is an AI-powered virtual front desk agent for clinics and hospitals. It handles patient calls, appointment scheduling, reminders (via WhatsApp), and integrates with Google Calendar and Plivo telephony.

---

## 🚀 Quick Start

### 1. Clone the Repository
   ```bash
git clone <your-repo-url>
cd syraa-t
```

### 2. Set Up Python Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Create a `.env` file in the project root with the following keys:

```
# Plivo (for calls and WhatsApp)
PLIVO_AUTH_ID=your_plivo_auth_id
PLIVO_AUTH_TOKEN=your_plivo_auth_token
PLIVO_PHONE_NUMBER=your_whatsapp_enabled_plivo_number

# Google Gemini
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-1.5-pro

# Supabase (for database)
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key

# Google Calendar
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_REDIRECT_URI=your_google_redirect_uri

# LiveKit (for SIP/voice)
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret

# Deepgram (for TTS/STT)
DEEPGRAM_API_KEY=your_deepgram_api_key
```

> **Note:** Your Plivo number must be WhatsApp-enabled. Phone numbers must be in E.164 format (e.g., `+1234567890`).

### 4. Google Calendar Setup
- Enable the Google Calendar API in Google Cloud Console.
- Download `credentials.json` and place it in the project root.
- The app will prompt for OAuth on first run.

### 5. Run the Server
```bash
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`.

---

## 🌐 Exposing Your Local Server (ngrok for Plivo Webhooks)

Plivo needs to reach your local FastAPI server for call and event webhooks. Use ngrok to expose your local server to the internet:

### 1. Start Your FastAPI Server
```bash
uvicorn main:app --reload
```

### 2. Start ngrok (Windows)
```bash
cd ngrok-v3-stable-windows-amd64
./ngrok.exe http 8000
```

### 3. Copy the HTTPS URL from ngrok output (e.g., `https://abcd1234.ngrok.io`).

### 4. Configure Plivo Webhooks
- In your Plivo dashboard, set the following URLs (replace with your ngrok URL):
  - **Answer URL:** `https://<ngrok-id>.ngrok.io/plivo/answer/`
  - **Event URL:** `https://<ngrok-id>.ngrok.io/plivo/events/`

> **Note:** You must keep ngrok running for Plivo to reach your server. Each time you restart ngrok, update the URLs in Plivo if they change.

---

## 💬 Example Usage

- **Inbound Call:**
  - Patient calls your Plivo number.
  - SYRAA answers, collects info, and books appointments.
  - Patient receives a WhatsApp reminder after booking.

- **API Health Check:**
  - Visit `http://localhost:8000/health` to check service status.

---

## 🛠️ Features
- AI receptionist (voice and text)
- Appointment scheduling, rescheduling, and cancellation
- Google Calendar sync
- WhatsApp reminders for appointments
- Patient memory and personalization
- Plivo telephony integration

---

## 🧩 Project Structure
- `main.py` – FastAPI app, telephony endpoints
- `appointment_service.py` – Appointment logic
- `patient_service.py` – Patient management
- `reminder_service.py` – WhatsApp reminders
- `calendar_service.py` – Google Calendar integration
- `database.py` – Supabase DB access
- `services/ai_service.py` – AI/LLM logic
- `knowledge_base/` – Clinic info and FAQs

---

## 📝 Notes
- All reminders are sent via WhatsApp (no voice reminders).
- Ensure all environment variables are set before running.
- For production, use HTTPS and secure your credentials.
- The Gemini model is selected via the GEMINI_MODEL environment variable (e.g., 'gemini-1.5-pro').

---

## 🤝 Support
For help, open an issue or contact the team.
