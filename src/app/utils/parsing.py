import re
from typing import Tuple, Optional

def parse_metric(text: str) -> Tuple[float, str]:
    """Extract numeric value and unit from text."""
    # Common patterns for fitness metrics
    patterns = [
        r'(\d+(?:\.\d+)?)\s*(km|m|calories|kcal|steps)',
        r'(\d+(?:\.\d+)?)\s*(kilometers|meters|calories|kilocalories)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text.lower())
        if match:
            value = float(match.group(1))
            unit = match.group(2)
            
            # Normalize units
            if unit in ['kilometers', 'km']:
                unit = 'km'
            elif unit in ['meters', 'm']:
                unit = 'm'
            elif unit in ['calories', 'kcal', 'kilocalories']:
                unit = 'calories'
                
            return value, unit
            
    raise ValueError("Could not extract metric from text")

def convert_units(value: float, from_unit: str, to_unit: str) -> float:
    """Convert between different units."""
    if from_unit == to_unit:
        return value
        
    conversions = {
        ('m', 'km'): lambda x: x / 1000,
        ('km', 'm'): lambda x: x * 1000,
        ('calories', 'kcal'): lambda x: x / 1000,
        ('kcal', 'calories'): lambda x: x * 1000,
    }
    
    if (from_unit, to_unit) in conversions:
        return conversions[(from_unit, to_unit)](value)
        
    raise ValueError(f"Cannot convert from {from_unit} to {to_unit}") 