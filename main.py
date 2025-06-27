import os
import logging
import google.generativeai as genai
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, HTMLResponse
from typing import Dict, Optional
from pydantic import BaseModel
from typing import Dict, Optional
from livekit import rtc, agents, api
from livekit.agents import (
    JobContext,
    JobRequest,
    WorkerOptions,
    Worker,
    cli,
)
from livekit.agents.tts import TTS
from livekit.agents.stt import STT
from livekit.plugins import deepgram
import asyncio
from dotenv import load_dotenv
import uuid
from plivo import RestClient
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("syraa")

# Load environment variables
load_dotenv()

# XML Templates
XML_RESPONSE = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Dial callerId="SYRAA" record="false">
        <User>sip:livekit-{call_uuid}@sip.plivo.com;transport=tcp</User>
    </Dial>
</Response>
"""

# This XML tells Plivo to connect the call to your LiveKit SIP trunk
# The call will be routed to the room specified in LiveKit's SIP configuration
# Make sure you've set up the SIP trunk in LiveKit with the Plivo SIP endpoint

# Note: The {call_uuid} ensures each call gets a unique SIP username
# Make sure you've set up a SIP trunk in LiveKit and configured the SIP endpoint in Plivo

# Initialize FastAPI app
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")  # e.g., 'gemini-1.5-pro'
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable not set")

genai.configure(api_key=GEMINI_API_KEY)

# Initialize Gemini model
try:
    logger.info(f"Using Gemini model: {GEMINI_MODEL_NAME} (set via GEMINI_MODEL env variable)")
    gemini_model = genai.GenerativeModel(GEMINI_MODEL_NAME)
except Exception as e:
    logger.error(f"Failed to initialize Gemini model: {e}")
    raise

# Store active calls
active_calls = {}

class CallStatus:
    CONNECTED = "connected"
    RINGING = "ringing"
    COMPLETED = "completed"
    FAILED = "failed"
    BUSY = "busy"
    NO_ANSWER = "no-answer"
    CANCELED = "canceled"

class CallDirection:
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    INTERNAL = "internal"

class CallRequest(BaseModel):
    to: str
    from_: str = None
    timeout: int = 30
    caller_id: str = None
    record: bool = False
    transcription: bool = True
    language: str = "en-US"
    metadata: Dict = {}

class CallResponse(BaseModel):
    call_sid: str
    status: str
    direction: str
    from_: str
    to: str
    start_time: str
    end_time: str = None
    duration: int = 0
    recording_url: str = None
    transcription_text: str = None
    metadata: Dict = {}

# Helper function to generate a unique call SID
def generate_call_sid() -> str:
    return str(uuid.uuid4())

# Helper function to generate LiveKit token
def generate_livekit_token(identity: str) -> str:
    """Generate LiveKit token for telephony integration"""
    # Get LiveKit API key and secret from environment variables
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")
    
    if not api_key or not api_secret:
        raise ValueError("LIVEKIT_API_KEY and LIVEKIT_API_SECRET must be set in environment variables")
    
    # Create a token with API access
    token = api.AccessToken(
        api_key=api_key,
        api_secret=api_secret,
    )
    
    # Set the identity (usually the phone number)
    token.identity = identity
    
    # For telephony, we need to enable room join and SIP
    grant = api.VideoGrant(
        room_join=True,
        room=identity,  # Use the phone number as room name
        can_publish=True,
        can_subscribe=True,
    )
    
    # Add the grant to the token
    token.with_grant(grant)
    
    # Generate and return the JWT token
    return token.to_jwt()

# Add a simple rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded. Please try again later."})

# Root endpoint
@app.get("/")
@limiter.limit("10/minute")
async def root(request: Request):
    """Root endpoint to check if the server is running"""
    return {
        "status": "ok",
        "message": "SYRAA API is running with direct SIP trunking",
        "version": "1.0.0"
    }

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "services": {
            "livekit": bool(os.getenv("LIVEKIT_API_KEY") and os.getenv("LIVEKIT_API_SECRET")),
            "plivo": True,
            "gemini": bool(GEMINI_API_KEY)
        }
    }

# Plivo Webhook Endpoints
@app.get("/plivo/answer")
@app.get("/plivo/answer/")
async def plivo_answer(request: Request):
    """Handle Plivo answer webhook"""
    # Get call data from query parameters
    call_data = dict(request.query_params)
    call_uuid = call_data.get('CallUUID', '')
    
    # Generate XML response with call UUID
    xml = XML_RESPONSE.format(
        call_uuid=call_uuid
    )
    
    logger.info(f"Plivo answer webhook received for call {call_uuid}")
    logger.debug(f"Call data: {call_data}")
    
    # Return XML response with correct content type
    return Response(
        content=xml,
        media_type="application/xml",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )

@app.post("/plivo/events/")
async def plivo_events(event: Dict):
    """Handle Plivo event webhook"""
    logger.info(f"Plivo event: {event}")
    return {"status": "ok"}

@app.get("/plivo/hangup/")
async def plivo_hangup(request: Request):
    """Handle Plivo hangup webhook"""
    call_data = dict(request.query_params)
    logger.info(f"Call ended: {call_data}")
    return {"status": "ok"}

# LiveKit Agent for handling SIP calls
class SyraaAgent:
    def __init__(self):
        # Get Deepgram API key from environment
        deepgram_api_key = os.getenv("DEEPGRAM_API_KEY")
        if not deepgram_api_key:
            raise ValueError("DEEPGRAM_API_KEY environment variable not set")
            
        # Initialize Deepgram TTS
        self.tts = deepgram.TTS(
            api_key=deepgram_api_key,
            voice="nova",  # or "shimmer" for a different voice
            model="aura-asteria-en"  # or other Deepgram models
        )
        
        # Initialize Deepgram STT
        self.stt = deepgram.STT(api_key=deepgram_api_key)
        
        # Store active calls
        self.active_calls = {}
        
        logger.info("SyraaAgent initialized with Deepgram TTS/STT")

    async def process_call(self, ctx: JobContext):
        """Process incoming SIP call"""
        room = ctx.room
        call_sid = room.name  # Using room name as call SID
        
        logger.info(f"Processing call in room: {room.name}")
        logger.info(f"Room SID: {room.sid}")
        
        try:
            # Connect to the room first
            await ctx.connect()
            logger.info("Connected to LiveKit room")
            
            # Get the participant (caller) - wait briefly for them to connect
            max_retries = 5
            participant = None
            for _ in range(max_retries):
                for p in room.participants.values():
                    if p.identity != "agent":  # Skip the agent itself
                        participant = p
                        break
                if participant:
                    break
                logger.info("Waiting for participant to connect...")
                await asyncio.sleep(1)
            
            if not participant:
                logger.error("No participant found in the room after retries")
                return
                
            logger.info(f"Found participant: {participant.identity}")
            
            # Store the call
            self.active_calls[call_sid] = {
                "participant": participant,
                "room": room,
                "status": "connected"
            }
            
            # Greet the caller
            await self.say("Hello! Thank you for calling SYRAA. How can I help you today?", participant)
            
            # Main conversation loop
            failed_attempts = 0
            MAX_FAILED_ATTEMPTS = 3
            while True:
                # Listen for user input
                user_text = await self.listen(participant)
                if not user_text:
                    failed_attempts += 1
                    if failed_attempts >= MAX_FAILED_ATTEMPTS:
                        await self.say("I'm having trouble understanding. Transferring you to a human agent.", participant)
                        await self.transfer_to_human(participant)
                        break
                    continue
                failed_attempts = 0
                logger.info(f"User said: {user_text}")
                
                # Get response from Gemini
                response = await self.get_gemini_response(user_text)
                
                if "human" in response.lower() or "agent" in response.lower() or "can't help" in response.lower():
                    await self.say("Transferring you to a human agent.", participant)
                    await self.transfer_to_human(participant)
                    break
                
                # Speak the response
                await self.say(response, participant)
                
        except Exception as e:
            logger.error(f"Error in call processing: {e}", exc_info=True)
            raise
        finally:
            # Clean up
            logger.info(f"Ending call {call_sid}")
            if call_sid in self.active_calls:
                del self.active_calls[call_sid]
            if room:
                await room.disconnect()
            logger.info("Call processing completed")
    
    async def say(self, text: str, participant):
        """Convert text to speech and play it to the participant using Deepgram TTS"""
        if not text:
            return
            
        try:
            # Generate speech with Deepgram TTS
            tts_stream = self.tts.synthesize(text)
            
            # Create audio track
            track = rtc.AudioTrack.create_audio_track(
                "agent_audio",
                sample_rate=tts_stream.sample_rate,
                num_channels=tts_stream.num_channels
            )
            
            # Publish the track
            publication = await participant.publish_track(track)
            
            # Stream the audio
            async for audio in tts_stream:
                track.push_frame(audio.frame)
                
            # Wait a bit for the audio to finish playing
            await asyncio.sleep(0.5)
            
            # Clean up
            await track.stop()
            
        except Exception as e:
            logger.error(f"Error in TTS: {e}", exc_info=True)
    
    async def listen(self, participant, timeout: float = 10.0) -> Optional[str]:
        """Listen for user speech and convert to text using Deepgram STT"""
        try:
            # Get the participant's audio track
            audio_track = None
            for track in participant.tracks.values():
                if track.kind == rtc.TrackKind.KIND_AUDIO:
                    audio_track = track
                    break
                    
            if not audio_track:
                logger.error("No audio track found for participant")
                return None
            
            # Create an audio stream
            audio_stream = rtc.AudioStream(
                sample_rate=16000,
                num_channels=1,
                samples_per_channel=320  # 20ms at 16kHz
            )
            
            # Subscribe to the participant's audio track
            audio_track.add_subscriber(audio_stream)
            
            # Create STT stream
            stt_stream = self.stt.recognize(
                audio_stream,
                language="en-US",
                interim_results=True,
                punctuate=True,
                model="nova-2"
            )
            
            # Process STT results with timeout
            try:
                start_time = asyncio.get_event_loop().time()
                
                async for result in stt_stream:
                    # Check timeout
                    if asyncio.get_event_loop().time() - start_time > timeout:
                        logger.info("Listening timed out")
                        return None
                        
                    if result.is_final and result.text.strip():
                        return result.text
                        
                return None
                
            except asyncio.TimeoutError:
                logger.info("Listening timed out")
                return None
                
        except Exception as e:
            logger.error(f"Error in STT: {e}", exc_info=True)
            return None
    
    async def get_gemini_response(self, prompt: str) -> str:
        """Get response from Gemini"""
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: gemini_model.generate_content(prompt)
            )
            return response.text or "I'm sorry, I didn't catch that. Could you please repeat?"
        except Exception as e:
            logger.error(f"Error getting response from Gemini: {e}")
            return "I'm sorry, I'm having trouble understanding. Could you please repeat that?"

    async def transfer_to_human(self, participant):
        """Transfer the call to a human agent using Plivo."""
        if not FALLBACK_PHONE_NUMBER:
            logger.error("FALLBACK_PHONE_NUMBER not set in environment.")
            await self.say("Sorry, no human agent is available at the moment.", participant)
            return
        try:
            client = RestClient(auth_id=os.getenv("PLIVO_AUTH_ID"), auth_token=os.getenv("PLIVO_AUTH_TOKEN"))
            response = client.calls.create(
                from_=os.getenv("PLIVO_PHONE_NUMBER"),
                to=FALLBACK_PHONE_NUMBER,
                answer_url="https://s3.amazonaws.com/static.plivo.com/answer.xml",
                answer_method="GET"
            )
            logger.info(f"Transferred call to human agent: [REDACTED], Plivo call UUID: {response['request_uuid']}")
        except Exception as e:
            logger.error(f"Failed to transfer call to human agent: {e}")
            await self.say("Sorry, we could not connect you to a human agent. Please try again later.", participant)

# Initialize LiveKit worker
async def entrypoint(ctx: JobContext):
    """LiveKit worker entrypoint for handling SIP calls"""
    agent = SyraaAgent()
    await agent.process_call(ctx)

# Run the worker if this file is executed directly
if __name__ == "__main__":
    import sys
    import threading
    import uvicorn
    
    # Create worker options
    worker_options = WorkerOptions(
        entrypoint_fnc=entrypoint,
    )
    
    # In production, you would typically run the worker separately from the API
    # For development, we'll run both in the same process
    if "--worker" in sys.argv:
        # Run only the worker (for production)
        print("Starting LiveKit worker in production mode...")
        sys.argv = [sys.argv[0], 'start']
        cli.run_app(worker_options)
    else:
        # For development, run both FastAPI and worker
        print("Starting in development mode...")
        
        # Start FastAPI in a separate thread
        def run_fastapi():
            uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
        
        fastapi_thread = threading.Thread(target=run_fastapi, daemon=True)
        fastapi_thread.start()
        
        # Run the worker in the main thread with dev command
        print("Starting LiveKit worker in development mode...")
        sys.argv = [sys.argv[0], 'dev']
        cli.run_app(worker_options)