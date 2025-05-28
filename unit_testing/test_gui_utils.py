import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from chatbot.gui_utils import extract_urls_from_text, is_valid_message_length, should_enable_send_button

# URL Extraction Tests
def test_extract_urls_none():
    text = "This message has no links."
    assert extract_urls_from_text(text) == []

def test_extract_single_url():
    text = "Please visit https://example.com for more info."
    assert extract_urls_from_text(text) == ["https://example.com"]

def test_extract_multiple_urls():
    text = "See https://a.com and http://b.org/page for references."
    assert extract_urls_from_text(text) == ["https://a.com", "http://b.org/page"]

# Message Length Validation Tests
def test_message_length_valid():
    assert is_valid_message_length("Hello world") is True

def test_message_length_too_long():
    assert is_valid_message_length("A" * 501) is False

# Send Button Enabling Logic Tests
def test_send_button_enabled_with_text():
    assert should_enable_send_button("message") is True

def test_send_button_disabled_empty():
    assert should_enable_send_button("   ") is False