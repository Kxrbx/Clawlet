"""
Utilities for masking sensitive data in logs.
"""

import re
from typing import Optional

# Patterns to detect secrets in strings
_SECRET_PATTERNS = [
    # Bearer tokens: "Bearer sk-...", "Bearer eyJ..."
    (re.compile(r'(Bearer\s+)([A-Za-z0-9\-_]+)', re.IGNORECASE), r'\1***'),
    # API keys: api_key=..., OPENROUTER_API_KEY=..., "api_key": "sk-..."
    (re.compile(r'(["\']?(api_key|token|password|secret)["\']?\s*[:\=]\s*["\']?)([A-Za-z0-9\-_/+]+)(["\']?)', re.IGNORECASE), r'\1***\4'),
    # Full tokens that look like base64: 32+ alphanumeric chars
    (re.compile(r'([A-Za-z0-9]{32,})'), lambda m: m.group(0) if len(m.group(0)) < 40 else '***'),
]

def mask_secrets(text: Optional[str]) -> Optional[str]:
    """
    Mask API keys, tokens, and passwords in a string.
    
    Args:
        text: The text to mask, or None
        
    Returns:
        Masked text, or None if input was None
    """
    if not text or not isinstance(text, str):
        return text
    
    result = text
    for pattern, replacement in _SECRET_PATTERNS:
        if callable(replacement):
            # Use a function to decide replacement dynamically
            result = pattern.sub(replacement, result)
        else:
            result = pattern.sub(replacement, result)
    
    return result
