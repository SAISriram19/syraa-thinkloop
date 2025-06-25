import os
from typing import Optional, Dict, Any
import google.generativeai as genai
from loguru import logger
from ..knowledge_base.manager import get_knowledge_base

class AIService:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")
        
        genai.configure(api_key=self.api_key)
        # Use the GEMINI_MODEL environment variable to select the Gemini model (e.g., 'gemini-1.5-pro')
        self.model = genai.GenerativeModel(os.getenv("GEMINI_MODEL", "gemini-1.5-pro"))
        self.knowledge_base = get_knowledge_base()
        self.conversation = self._start_conversation()
    
    def _start_conversation(self):
        """Start a new conversation with context from the knowledge base."""
        system_prompt = """You are SYRAA, an AI receptionist for a medical clinic. Your role is to assist 
        patients with appointment scheduling, answering questions about the clinic, and providing helpful 
        information. Be professional, empathetic, and concise in your responses.
        
        When scheduling appointments, always confirm:
        1. Patient's name
        2. Preferred date and time
        3. Reason for visit
        4. Preferred doctor (if any)
        
        If any information is missing, politely ask for clarification.
        """
        
        # Add clinic-specific context
        clinic_context = self.knowledge_base.generate_context_prompt()
        
        # Combine with system prompt
        full_context = f"{system_prompt}\n\n{clinic_context}"
        
        # Start the conversation with the model
        return self.model.start_chat(history=[
            {"role": "user", "parts": [full_context]},
            {"role": "model", "parts": ["I understand. I'm ready to assist patients with their needs."]}
        ])
    
    async def process_message(self, message: str, conversation_id: Optional[str] = None) -> str:
        """
        Process a user message and return the AI's response.
        
        Args:
            message: The user's message
            conversation_id: Optional ID to maintain conversation context
            
        Returns:
            str: The AI's response
        """
        try:
            # Add conversation history if conversation_id is provided
            # (Implementation depends on how you're storing conversation state)
            
            # Get response from the model
            response = self.conversation.send_message(message)
            return response.text
            
        except Exception as e:
            logger.error(f"Error generating AI response: {e}")
            return "I'm sorry, I'm having trouble processing your request. Please try again later."
    
    async def extract_appointment_details(self, message: str) -> Dict[str, Any]:
        """
        Extract appointment details from a user's message.
        
        Returns a dictionary with:
        - intent: 'schedule', 'reschedule', 'cancel', or 'other'
        - details: Extracted information
        - missing_info: List of missing required fields
        """
        prompt = f"""
        Analyze the following message from a patient and extract appointment details.
        
        Message: "{message}"
        
        Return a JSON object with:
        - intent: One of 'schedule', 'reschedule', 'cancel', or 'other'
        - details: Object with extracted fields (date, time, doctor, reason, etc.)
        - missing_info: List of missing required fields
        
        Only return the JSON object, no other text.
        """
        
        try:
            response = self.model.generate_content(prompt)
            # Parse the response as JSON
            import json
            result = json.loads(response.text.strip())
            return result
            
        except Exception as e:
            logger.error(f"Error extracting appointment details: {e}")
            return {
                "intent": "other",
                "details": {},
                "missing_info": []
            }

# Singleton instance
_ai_service = None

def get_ai_service() -> AIService:
    """Get the AI service instance."""
    global _ai_service
    if _ai_service is None:
        _ai_service = AIService()
    return _ai_service
