import re
from typing import List

def extract_urls_from_text(text: str) -> List[str]:
    pattern = re.compile(r"(https?://\S+)")
    return pattern.findall(text)

def is_valid_message_length(text: str, limit: int = 500) -> bool:
    return len(text.strip()) <= limit

def should_enable_send_button(text: str) -> bool:
    return bool(text.strip())