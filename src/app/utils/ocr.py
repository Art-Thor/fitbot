import pytesseract
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import io
import requests
from typing import Optional, Tuple
import logging
from tenacity import retry, stop_after_attempt, wait_exponential
from ..config import settings
from .logging import setup_logger

logger = setup_logger(__name__)

def preprocess_image(image: Image.Image) -> Image.Image:
    """Apply preprocessing to improve OCR accuracy."""
    # Convert to grayscale
    image = image.convert('L')
    
    # Enhance contrast
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(2.0)
    
    # Apply median filter to reduce noise
    image = image.filter(ImageFilter.MedianFilter(size=3))
    
    return image


async def process_screenshot(url: str) -> Optional[float]:
    """Download and process a screenshot to extract the numeric value."""
    try:
        # Download the image
        response = requests.get(url)
        response.raise_for_status()
        
        # Open and preprocess the image
        image = Image.open(io.BytesIO(response.content))
        processed_image = preprocess_image(image)
        
        # Perform OCR
        text = pytesseract.image_to_string(processed_image)
        
        # Extract numeric value
        # This is a simple implementation - you might want to make it more robust
        try:
            value = float(''.join(filter(lambda x: x.isdigit() or x == '.', text)))
            return value
        except ValueError:
            return None
            
    except Exception as e:
        print(f"Error processing screenshot: {e}")
        return None


def validate_result(claimed_value: float, ocr_value: float, tolerance: float = None) -> Tuple[bool, Optional[str]]:
    """Validate if the OCR value matches the claimed value within tolerance."""
    if tolerance is None:
        tolerance = settings.ocr_validation_tolerance
        
    if ocr_value is None:
        return False, "Could not extract value from screenshot"
    
    difference = abs(claimed_value - ocr_value)
    if difference <= (claimed_value * tolerance):
        return True, None
    else:
        return False, f"Value mismatch: claimed {claimed_value}, found {ocr_value} (tolerance: {tolerance * 100}%)"


class VisionService:
    def __init__(self):
        self.tolerance = settings.ocr_validation_tolerance
        logger.info(f"Initialized VisionService with tolerance {self.tolerance * 100}%")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True
    )
    def download_image(self, url: str, token: str) -> bytes:
        """Download image from Slack with retry logic."""
        try:
            logger.debug(f"Downloading image from {url}")
            response = requests.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
                timeout=(3, 10)
            )
            response.raise_for_status()
            logger.debug("Image downloaded successfully")
            return response.content
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to download image from {url}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error downloading image: {e}")
            raise

    def preprocess_image(self, image: Image.Image) -> Image.Image:
        """Preprocess image for better OCR results."""
        try:
            logger.debug("Starting image preprocessing")
            
            # Convert to grayscale
            image = image.convert('L')
            logger.debug("Converted to grayscale")
            
            # Increase contrast
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(2.0)
            logger.debug("Enhanced contrast")
            
            # Apply median filter to reduce noise
            image = image.filter(ImageFilter.MedianFilter(size=3))
            logger.debug("Applied median filter")
            
            # Apply threshold to make text more distinct
            image = ImageOps.autocontrast(image)
            logger.debug("Applied auto-contrast")
            
            return image
        except Exception as e:
            logger.error(f"Error in image preprocessing: {e}")
            raise

    def analyze(self, image_bytes: bytes, claimed_value: float = None) -> Optional[float]:
        """Analyze image and extract numeric value."""
        try:
            logger.debug("Starting OCR analysis")
            
            # Load and preprocess image
            image = Image.open(io.BytesIO(image_bytes))
            processed = self.preprocess_image(image)
            
            # Extract text
            text = pytesseract.image_to_string(processed)
            logger.debug(f"OCR extracted text: {text}")
            
            # Parse numeric value
            import re
            numbers = re.findall(r'\d+\.?\d*', text)
            if not numbers:
                logger.warning("No numbers found in OCR text")
                return None
                
            value = float(numbers[0])
            logger.debug(f"Extracted value: {value}")
            
            # Validate against claimed value if provided
            if claimed_value is not None:
                difference = abs(value - claimed_value) / claimed_value
                logger.debug(f"Value difference: {difference * 100:.1f}%")
                
                if difference > self.tolerance:
                    logger.warning(
                        f"OCR value {value} differs significantly from claimed value {claimed_value} "
                        f"(tolerance: {self.tolerance * 100}%)"
                    )
                    return None
                    
            return value
            
        except Exception as e:
            logger.error(f"Error in OCR analysis: {e}")
            return None 