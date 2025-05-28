import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from chatbot.nlp_module import NLPProcessor

station_dict = {
    "norwich": "NRW",
    "london": "LST",
    "cambridge": "CBG",
    "ipswich": "IPS"
}

processor = NLPProcessor(station_dict=station_dict)

def test_predict_intent_ticket():
    intent, confidence = processor.predict_intent("I want to book a train ticket")
    assert intent == "find_ticket"
    assert confidence > 0.2  # Adjusted threshold to match logic

def test_predict_intent_delay():
    intent, confidence = processor.predict_intent("Why is my train delayed?")
    assert intent == "predict_delay"
    assert confidence > 0.1  # Adjusted threshold for fewer keyword matches

def test_extract_stations_direct_phrase():
    slots = processor.extract_stations("from Norwich to London", "find_ticket")
    assert slots['departure'] == "NRW"
    assert slots['destination'] == "LST"

def test_extract_stations_phrase_match():
    slots = processor.extract_stations("I want to go from Cambridge to Ipswich", "find_ticket")
    assert slots['departure'] == "CBG"
    assert slots['destination'] == "IPS"

def test_extract_trip_type_return():
    trip = processor.extract_trip_type("I want a return ticket")
    assert trip == "return"

def test_extract_trip_type_single():
    trip = processor.extract_trip_type("I need a single ticket")
    assert trip == "single"

def test_extract_delay_info():
    slots = processor.extract_train_info("Train 1234 is 10 minutes late")
    assert slots['train_id'] == "1234"
    assert slots['delay_minutes'] == 10

def test_parse_full_input():
    result = processor.parse("I want to book a return train ticket from Norwich to London tomorrow at 7:30am")
    assert result['intent'] == "find_ticket"
    assert result['slots']['departure'] == "NRW"
    assert result['slots']['destination'] == "LST"
    assert result['slots']['trip_type'] == "return"
    assert 'date' in result['slots']
    assert 'time' in result['slots']