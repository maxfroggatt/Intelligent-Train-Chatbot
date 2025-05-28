import csv
import re
import logging
import spacy
import difflib
import dateparser
from spacy.matcher import PhraseMatcher
from dateparser.search import search_dates
from pathlib import Path
from services.stations_loader import load_station_dict
from datetime import datetime, date, timedelta, time as dptime
from pathlib import Path

# Load station names and aliases mapped to codes
def load_station_dict(csv_path: Path) -> dict[str, str]:
    station_map: dict[str, str] = {}

    # Check if the file exists
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)

        # Skip the header row
        for row in reader:
            if len(row) < 5:
                continue
            official, longname, alias, alpha3, tiploc = row
            code = alpha3.strip() or tiploc.strip()
            # Skip if no code is provided
            if not code or code == "\\N":
                continue
            for key in (official, longname, alias):
                if key and key != "\\N":
                    station_map[key.lower()] = code
    return station_map

# Initialize NLP with station names and intent patterns
class NLPProcessor:
    def __init__(self, station_dict: dict[str, str] = None, stations_csv_path: str = None):
        self.logger = logging.getLogger(__name__)
        self.nlp = spacy.load("en_core_web_sm")

        # Load station dictionary from CSV if provided
        if station_dict is None and stations_csv_path:
            station_dict = load_station_dict(Path(stations_csv_path))
        self.stations = station_dict or {
            "norwich": "NWI",
            "london": "LST",
            "oxford": "OXF",
            "ipswich": "IPS"
        }

        # PhraseMatcher setup
        self.matcher = PhraseMatcher(self.nlp.vocab, attr="LOWER")
        patterns = [self.nlp.make_doc(name) for name in self.stations.keys()]
        self.matcher.add("STATION", patterns)

        # Intent keywords
        self.intent_keywords = {
            "find_ticket": ["ticket", "price", "journey", "cheapest", "book", "train", "travel", "trip", "fare"],
            "predict_delay": ["delay", "late", "arrival", "predict", "delayed"]
        }

        # Precompile regex
        self._pat_return = re.compile(r"\b(return|back)\b", re.IGNORECASE)
        self._pat_single = re.compile(r"\b(single|one[- ]way)\b", re.IGNORECASE)
        self._pat_train = re.compile(r"train\s*(\d+)", re.IGNORECASE)
        self._pat_delay = re.compile(r"(\d+)\s*minutes?", re.IGNORECASE)

    # Predict intent based on keywords
    def predict_intent(self, text: str) -> tuple[str, float]:
        txt = text.lower()
        scores = {intent: sum(1 for kw in kws if kw in txt) for intent, kws in self.intent_keywords.items()}
        best_intent, best_score = max(scores.items(), key=lambda x: x[1])
        total = sum(len(kws) for kws in self.intent_keywords.values())
        confidence = best_score / total if total else 0.0

        # Log the prediction
        if best_score == 0:
            return "unsupported", confidence
        return best_intent, confidence

    # Extract adult and child counts from text
    def extract_passenger_counts(self, text: str) -> dict:
        slots = {}

        # Normalize for matching
        lower = text.lower()

        # Simple regex patterns
        adult_match = re.search(r'(\d+)\s+adult[s]?', lower)
        child_match = re.search(r'(\d+)\s+child(?:ren)?', lower)

        # Handle special cases
        if "only me" in lower or "just me" in lower or "only one ticket" in lower:
            slots["adults"] = 1
            slots["children"] = 0
        elif "just adults" in lower or "no children" in lower:
            slots["adults"] = int(adult_match.group(1)) if adult_match else 1
            slots["children"] = 0
        else:
            if adult_match:
                slots["adults"] = int(adult_match.group(1))
            if child_match:
                slots["children"] = int(child_match.group(1))

        return slots

    # Extract dates and times from user text
    def extract_datetimes(self, text: str) -> dict:
        slots = {}
        now = datetime.now()
        low_text = text.lower()

        # Literal "today"/"tonight"
        if "today" in low_text or "tonight" in low_text:
            slots['date'] = now.date()
        # Literal "tomorrow"
        elif "tomorrow" in low_text:
            slots['date'] = (now + timedelta(days=1)).date()

        # Extract time via regex
        t_re = re.compile(r'\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b', re.IGNORECASE)
        t_match = t_re.search(text)
        if t_match:
            h = int(t_match.group(1))
            m = int(t_match.group(2) or 0)
            ampm = t_match.group(3)
            if ampm:
                if ampm.lower() == 'pm' and h < 12: h += 12
                if ampm.lower() == 'am' and h == 12: h = 0
            slots['time'] = dptime(hour=h, minute=m)
            text = text.replace(t_match.group(0), '')

        # Extract date via dateparser on the remaining text
        date_re = re.compile(
            r'\b(\d{1,2}(?:st|nd|rd|th)?(?: of)? [A-Za-z]+(?: \d{4})?|\d{4}-\d{2}-\d{2})\b',
            re.IGNORECASE
        )
        d_match = date_re.search(text)

        # If no date found, try dateparser search
        if d_match:
            dt = dateparser.parse(
                d_match.group(1),
                settings={
                    "PREFER_DATES_FROM": "future",
                    "DATE_ORDER": "DMY",
                    "RELATIVE_BASE": now
                }
            )

            # If dateparser found a date, check if it's in the past
            if dt:
                parsed_date = dt.date()
                if parsed_date < now.date():
                    parsed_date = parsed_date.replace(year=parsed_date.year + 1)
                slots['date'] = parsed_date
                text = text.replace(d_match.group(0), '')

        return slots

    # Extract station names and map to codes based on intent
    def extract_stations(self, text: str, intent: str) -> dict:
        doc = self.nlp(text)
        matches = self.matcher(doc)
        found = [doc[start:end].text.lower() for _, start, end in matches]
        unique = list(dict.fromkeys(found))
        slots = {}

        # If no stations found, return empty slots
        if intent == 'predict_delay':
            if unique:
                slots['current_station'] = self.stations[unique[0]]
            if len(unique) > 1:
                slots['destination'] = self.stations[unique[1]]

        # If intent is find_ticket, extract departure and destination
        else:
            frmto = re.search(r"from\s+([A-Za-z ]+?)\s+to\s+([A-Za-z ]+?)\b", text, re.IGNORECASE)
            if frmto:
                dep = frmto.group(1).strip().lower();
                dst = frmto.group(2).strip().lower()
                dc = self.stations.get(dep);
                ec = self.stations.get(dst)
                if dc and ec:
                    return {'departure': dc, 'destination': ec}

            # If no explicit from to found, use the unique stations
            if len(unique) >= 2:
                slots['departure'] = self.stations[unique[0]]
                slots['destination'] = self.stations[unique[1]]
            elif unique:
                slots['stations'] = [self.stations[unique[0]]]

        # fuzzy fallback
        if not slots and len(text) < 40:
            cand = difflib.get_close_matches(text.lower(), self.stations.keys(), n=1, cutoff=0.8)
            if cand:
                slots['stations'] = [self.stations[cand[0]]]
        return slots

    # Determine if trip is single or return
    def extract_trip_type(self, text: str) -> str | None:
        if self._pat_return.search(text): return 'return'
        if self._pat_single.search(text): return 'single'
        return None

    # Extract train ID and delay minutes from text
    def extract_train_info(self, text: str) -> dict:
        slots = {}
        tid = self._pat_train.search(text)
        if tid: slots['train_id'] = tid.group(1)
        dm = self._pat_delay.search(text)
        if dm: slots['delay_minutes'] = int(dm.group(1))
        return slots

    # Parse user text into intent and slots with fallbacks
    def parse(self, text: str) -> dict:
        intent, conf = self.predict_intent(text)
        slots = {}
        datetime_slots = self.extract_datetimes(text)

        # If no date or time found, use current date and time
        if "date" in datetime_slots:
            datetime_slots["date"] = datetime_slots["date"].isoformat()
        if "time" in datetime_slots:
            datetime_slots["time"] = datetime_slots["time"]
        slots.update(datetime_slots)
        slots.update(self.extract_stations(text, intent))
        tp = self.extract_trip_type(text)

        # Extract train ID and delay minutes if applicable
        if tp: slots['trip_type'] = tp
        slots.update(self.extract_passenger_counts(text))

        # predict delay intent 
        if intent == "predict_delay" and not {"rid", "station", "reported_delay", "destination"} <= slots.keys():
            print(f"[DEBUG] Raw input for fallback: {text!r}")
            print("[DEBUG] Triggering fallback CSV matcher for delay prediction input...")

        # Fallback for delay prediction intent using CSV-like format
        csv_match = re.search(
            r"^\s*([\w\d]+)[,\s]+([A-Za-z]{3})[,\s]+(\d+)[,\s]+([A-Za-z]{3})",
            text.strip(), re.IGNORECASE
        )

        # If CSV-like format matches, extract values
        if csv_match:
            slots["rid"] = csv_match.group(1)
            slots["station"] = csv_match.group(2).upper()
            slots["reported_delay"] = float(csv_match.group(3))
            slots["destination"] = csv_match.group(4).upper()
            print(
                f"[DEBUG] Matched values - rid: {slots['rid']}, station: {slots['station']}, delay: {slots['reported_delay']}, dest: {slots['destination']}")

        # Always normalize slot keys
        if 'train_id' in slots and 'rid' not in slots:
            slots['rid'] = slots.pop('train_id')
        if 'delay_minutes' in slots and 'reported_delay' not in slots:
            slots['reported_delay'] = slots.pop('delay_minutes')
        if 'current_station' in slots and 'station' not in slots:
            slots['station'] = slots.pop('current_station')

        return {'intent': intent, 'confidence': conf, 'slots': slots}

    # Identify missing slots required for an intent
    def missing_slots(self, intent: str, slots: dict) -> list[str]:
        reqs = {'find_ticket': ['departure', 'destination', 'date', 'trip_type'],
                'predict_delay': ['rid', 'station', 'reported_delay', 'destination']}
        return [k for k in reqs.get(intent, []) if k not in slots]