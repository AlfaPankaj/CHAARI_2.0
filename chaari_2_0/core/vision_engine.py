# CHAARI 2.0 — ASUS Host — Vision Engine
# ═══════════════════════════════════════════════════════════
# Responsibility:
#   ✔ Interface with Ollama's Llava model
#   ✔ Perform visual reasoning on Base64 image data
#   ✔ Return natural language description of visual context
# ═══════════════════════════════════════════════════════════

import requests
import logging

logger = logging.getLogger("chaari.asus.vision")

class VisionEngine:
    """ASUS-side engine for visual reasoning using Llava."""

    def __init__(self, ollama_url="http://127.0.0.1:11434", model="llava:7b"):
        self.url = f"{ollama_url}/api/generate"
        self.model = model

    def analyze_image(self, base64_image: str, prompt: str = "Describe what is on the screen in detail. Focus on active applications, text, and any errors.") -> str:
        """
        Send image to local Llava model for analysis.
        
        Args:
            base64_image: The image data from Dell node
            prompt: Question or instruction for the vision model
            
        Returns:
            Text description from Llava
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "images": [base64_image]
        }

        try:
            logger.info(f"Sending image to vision model: {self.model}")
            response = requests.post(self.url, json=payload, timeout=120)
            response.raise_for_status()
            
            data = response.json()
            description = data.get("response", "").strip()
            
            if not description:
                return "I saw the screen but couldn't quite make out what's happening, Boss."
                
            return description

        except requests.exceptions.RequestException as e:
            logger.error(f"Vision Engine error: {e}")
            return f"Sorry Boss, mere eyes (vision model) kaam nahi kar rahe right now. Error: {e}"
        except Exception as e:
            logger.error(f"Unexpected vision error: {e}")
            return "Kuch toh gadbad hai visual analysis mein."
