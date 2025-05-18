import requests
from tenacity import retry, stop_after_attempt, wait_exponential
from ..config import settings
from ..utils.logging import setup_logger

logger = setup_logger(__name__)

class OllamaClient:
    def __init__(self):
        self.base_url = settings.ollama_url
        self.model = "llama2"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True
    )
    def call_ollama(self, prompt: str) -> str:
        """Call Ollama API with retry logic."""
        try:
            response = requests.post(
                f"{self.base_url}/api/run",
                json={
                    "model": self.model,
                    "prompt": prompt
                },
                timeout=(3, 10)
            )
            response.raise_for_status()
            return response.json()["completion"]
        except Exception as e:
            logger.error(f"Failed to call Ollama API: {e}")
            raise

    def extract_metrics(self, text: str) -> dict:
        """Extract date and discipline from text using Ollama."""
        prompt = f"""Extract the following information from the text:
        - Date (in YYYY-MM-DD format)
        - Discipline (e.g., running, cycling, swimming)
        - Value (numeric)
        - Unit (e.g., km, min, reps)
        
        Text: {text}
        
        Return the result in JSON format:
        {{
            "date": "YYYY-MM-DD",
            "discipline": "string",
            "value": number,
            "unit": "string"
        }}
        """
        
        try:
            result = self.call_ollama(prompt)
            logger.debug(f"Ollama extracted metrics: {result}")
            return result
        except Exception as e:
            logger.error(f"Failed to extract metrics: {e}")
            return None 