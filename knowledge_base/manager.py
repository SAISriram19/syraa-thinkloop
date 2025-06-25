import json
from pathlib import Path
from typing import Dict, Any, Optional
from loguru import logger

class KnowledgeBaseManager:
    def __init__(self, knowledge_base_dir: str = "knowledge_base"):
        self.knowledge_base_dir = Path(knowledge_base_dir)
        self.knowledge_base_dir.mkdir(exist_ok=True)
        self.clinic_info = self._load_clinic_info()
    
    def _load_clinic_info(self) -> Dict[str, Any]:
        """Load clinic information from JSON file."""
        clinic_info_path = self.knowledge_base_dir / "clinic_info.json"
        try:
            with open(clinic_info_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"Clinic info not found at {clinic_info_path}")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing clinic info JSON: {e}")
            return {}
    
    def get_clinic_info(self) -> Dict[str, Any]:
        """Get all clinic information."""
        return self.clinic_info
    
    def get_doctor_info(self, doctor_id: str = None, name: str = None) -> Optional[Dict[str, Any]]:
        """Get information about a specific doctor by ID or name."""
        if not self.clinic_info.get('doctors'):
            return None
            
        for doctor in self.clinic_info['doctors']:
            if (doctor_id and doctor.get('id') == doctor_id) or \
               (name and name.lower() in doctor.get('name', '').lower()):
                return doctor
        return None
    
    def get_operating_hours(self) -> Dict[str, str]:
        """Get clinic operating hours."""
        return self.clinic_info.get('hours', {})
    
    def get_services(self) -> list:
        """Get list of services offered by the clinic."""
        return self.clinic_info.get('services', [])
    
    def get_insurance_providers(self) -> list:
        """Get list of accepted insurance providers."""
        return self.clinic_info.get('insurance_accepted', [])
    
    def get_faqs(self) -> list:
        """Get frequently asked questions and answers."""
        return self.clinic_info.get('faqs', [])
    
    def generate_context_prompt(self) -> str:
        """Generate a context prompt for the AI with clinic information."""
        if not self.clinic_info:
            return ""
        
        context_parts = [
            f"You are an AI assistant for {self.clinic_info.get('clinic_name', 'our clinic')}.",
            f"Clinic Address: {self.clinic_info.get('address')}",
            f"Phone: {self.clinic_info.get('phone')}",
            "\nOperating Hours:"
        ]
        
        # Add operating hours
        for day, hours in self.clinic_info.get('hours', {}).items():
            context_parts.append(f"- {day.capitalize()}: {hours}")
        
        # Add services
        if 'services' in self.clinic_info:
            context_parts.append("\nServices we offer:")
            for service in self.clinic_info['services']:
                context_parts.append(f"- {service}")
        
        # Add doctors
        if 'doctors' in self.clinic_info:
            context_parts.append("\nOur Doctors:")
            for doctor in self.clinic_info['doctors']:
                context_parts.append(
                    f"- {doctor['name']} ({doctor['specialty']}): {doctor['bio']}"
                )
        
        # Add insurance info
        if 'insurance_accepted' in self.clinic_info:
            context_parts.append(
                f"\nWe accept the following insurance: {', '.join(self.clinic_info['insurance_accepted'])}"
            )
        
        # Add FAQs
        if 'faqs' in self.clinic_info and self.clinic_info['faqs']:
            context_parts.append("\nFrequently Asked Questions:")
            for faq in self.clinic_info['faqs']:
                context_parts.append(f"Q: {faq['question']}")
                context_parts.append(f"A: {faq['answer']}\n")
        
        return "\n".join(context_parts)

# Singleton instance
knowledge_base = KnowledgeBaseManager()

def get_knowledge_base() -> KnowledgeBaseManager:
    """Get the knowledge base instance."""
    return knowledge_base
