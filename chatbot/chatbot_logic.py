import logging
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from .nlp_module import NLPProcessor
from scrapers.national_rail_scraper import plan_journey_with_cheapest_ticket
from datetime import datetime, date
from .delay_predictor import predict_arrival_time
from .get_prediction_schedule import get_prediction_schedule
from datetime import datetime

# Utility function to parse service date from different formats
def parse_service_date(date_str):
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognized date format: {date_str!r}")

# Converts chatbot slot values to valid inputs for the web scraper
def prepare_and_plan_journey(slots: dict):
    from datetime import datetime

    # Departure info
    origin = slots["departure"]
    destination = slots["destination"]

    dep_date_obj = datetime.fromisoformat(slots["date"])
    dep_date = dep_date_obj.strftime("%d/%m/%Y")

    # Handle if 'time' is a string or datetime.time
    time_obj = slots["time"]
    if isinstance(time_obj, str):
        dep_hour, dep_min = time_obj.split(":")
    else:
        dep_hour = str(time_obj.hour).zfill(2)
        dep_min = str(time_obj.minute).zfill(2)

    # Ticket info
    adults = str(slots.get("adults", 1))
    children = str(slots.get("children", 0))

    # Return journey
    if slots.get("trip_type") == "return":
        return_date_obj = datetime.fromisoformat(slots["return_date"])
        return_date = return_date_obj.strftime("%d/%m/%Y")
        ret_time = slots["return_time"]
        if isinstance(ret_time, str):
            return_hour, return_min = ret_time.split(":")
        else:
            return_hour = str(ret_time.hour).zfill(2)
            return_min = str(ret_time.minute).zfill(2)
    else:
        return_date = dep_date
        return_hour = "00"
        return_min = "00"

    # Determine if it's a return journey
    is_return = slots.get("trip_type") == "return"

    # Run scraper
    result = plan_journey_with_cheapest_ticket(
        origin, destination,
        dep_date, dep_hour, dep_min,
        return_date, return_hour, return_min,
        adults, children, is_return
    )

    # Wrap scraper result in a simple class
    class Result:
        def __init__(self, data):
            self.price = data.get("cheapest_price", 0.0)
            self.url = data.get("booking_url", "")

    return Result(result)

# Chatbot class logic handling dialogue state, external calls, and responses
class Chatbot:
    # Initialize chatbot with NLP and thread pool
    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # Load NLP with full station list
        self.nlp = NLPProcessor(stations_csv_path="task2_v4/data/stations.csv")
        self.executor = ThreadPoolExecutor(max_workers=2)
        self._reset_state()

    # Reset chatbot dialogue state
    def _reset_state(self):
        self.state = {"intent": None, "slots": {}}
        self.confirm_done = False

    # Convert number words to integers
    def _word_to_number(self, text: str) -> int | None:
        word_map = {
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "zero": 0
        }
        return word_map.get(text.lower())

    # Respond to user input and manage dialogue state
    def respond(self, user_text: str) -> str:
        raw = user_text.strip()
        text = raw.lower()

        # Handle standalone return queries using last_journey context
        if (self.state.get("intent") is None
                and any(k in text for k in ("return", "back"))
                and getattr(self, 'last_journey', None)
        ):

            # Set up return leg from previous journey
            lj = self.last_journey
            self.state["intent"] = "find_ticket"
            self.confirm_done = True  # skip station confirmation

            # departure becomes previous destination, and vice versa
            self.state["slots"] = {
                "departure": lj['destination_code'],
                "destination": lj['departure_code'],
                "trip_type": "return"
            }

        slots = self.state.get("slots", {})

        # Contextual return-date/time capture ONLY if trip_type is return
        if (self.state.get("intent") == "find_ticket"
                and self.confirm_done
                and slots.get("trip_type") == "return"
        ):

            # Capture return_date
            if "return_date" not in slots:
                from dateparser import parse as dp_parse
                rd = dp_parse(raw, settings={"PREFER_DATES_FROM": "future", "DATE_ORDER": "DMY"})
                if rd:
                    slots["return_date"] = rd.date().isoformat()
                return self._handle_find_ticket(raw)

            # Capture return_time
            if "return_date" in slots and "return_time" not in slots:
                tm = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", raw, re.IGNORECASE)
                if tm:
                    h = int(tm.group(1))
                    m = int(tm.group(2) or 0)
                    ap = tm.group(3)
                    if ap:
                        if ap.lower() == "pm" and h < 12: h += 12
                        if ap.lower() == "am" and h == 12: h = 0
                    slots["return_time"] = f"{h:02d}:{m:02d}"
                return self._handle_find_ticket(raw)

        # Waiting for station confirmation response
        if self.state.get("intent") == "find_ticket" and not self.confirm_done:
            if re.match(r'^(yes|y|correct|right)\b', text):
                self.logger.info("User confirmed stations")
                self.confirm_done = True
                return self._handle_find_ticket(raw)
            if re.match(r'^(no|n)\b', text) or "not correct" in text:
                self.logger.info("User denied station confirmation")
                slots = self.state["slots"]
                slots.pop("departure", None)
                slots.pop("destination", None)
                return "(Info needed) Where are you departing from?"

        # Preprocess date/time for outbound, ONLY if not already confirmed
        if (self.state.get("intent") in (None, "find_ticket")
                and not self.confirm_done):
            from datetime import time as dptime
            import dateparser.search

            today = datetime.now().date()
            slots = self.state.setdefault("slots", {})
            dt_matches = dateparser.search.search_dates(
                raw,
                settings={
                    "PREFER_DATES_FROM": "future",
                    "DATE_ORDER": "DMY",
                    "RELATIVE_BASE": datetime.now()
                }
            ) or []

            date_assigned = False
            time_assigned = False
            removals = []
            for phrase, dt in dt_matches:

                # Assign time slot if detected in input
                if dt.time() != dptime.min and "time" not in slots and not time_assigned:
                    slots["time"] = dt.strftime("%H:%M")
                    time_assigned = True
                    removals.append(phrase)
                    continue

                # Assign date slot if detected in input
                if dt.date() != today and dt.time() == dptime.min and "date" not in slots and not date_assigned:
                    slots["date"] = dt.date().isoformat()
                    date_assigned = True
                    removals.append(phrase)
                    continue

            # Remove processed date/time phrases from input
            for phrase in removals:
                raw = raw.replace(phrase, "").strip()
            text = raw.lower()

        # Standard NLP parse
        parsed = self.nlp.parse(raw)
        intent = parsed["intent"]
        confidence = parsed["confidence"]
        new_slots = parsed["slots"]
        self.logger.debug(f"Parsed intent={intent} (conf={confidence:.2f}), slots={new_slots}")

        # First turn fallback
        if self.state["intent"] is None:
            if intent == "unsupported" or confidence < 0.05:
                self.logger.info("Fallback on first turn: unsupported or low confidence")
                self._reset_state()
                return (
                    "Sorry, I can only help with UK train enquiries. "
                    "Could you rephrase or ask about train tickets or delays?"
                )
            self.state["intent"] = intent

        # Merge slots (but don't overwrite existing ones)
        for key, value in new_slots.items():
            if key not in self.state["slots"]:
                self.state["slots"][key] = value

        # Route to find_ticket
        if self.state["intent"] == "find_ticket":
            return self._handle_find_ticket(raw)

        # Route to delay prediction
        if self.state["intent"] == "predict_delay":
            return self._handle_predict_delay()

        # Generic fallback
        self._reset_state()
        return "Sorry, I don't know how to help with that."

    # Slot-filling and ticket lookup logic with return handling
    def _handle_find_ticket(self, user_input: str) -> str:
        s = self.state["slots"]
        normalized_input = user_input.strip().lower()

        # Handle ambiguous station matches
        if "stations" in s:
            codes = s["stations"]
            if len(codes) > 1:
                code_to_name = {c: name.title().replace(" Rail Station", "")
                                for name, c in self.nlp.stations.items() if c in codes}
                label = "departure station" if "departure" not in s else "destination station"
                return (
                    f"(Info needed) I found multiple {label} matches: "
                    f"{', '.join(code_to_name.values())}. Which one did you mean?"
                )
            sel = codes[0]
            s.pop("stations")
            if "departure" not in s:
                s["departure"] = sel
            else:
                s["destination"] = sel

        # Build reverse map
        code_to_name = {c: name.title().replace(" Rail Station", "")
                        for name, c in self.nlp.stations.items()}

        # Detailed confirmation
        if not self.confirm_done:

            # default date to today if only time provided
            if "time" in s and "date" not in s:
                s["date"] = date.today().isoformat()
            if "departure" in s and "destination" in s:
                dep = code_to_name[s["departure"]]
                dst = code_to_name[s["destination"]]
                parts = [f"from {dep} to {dst}"]
                if "date" in s:
                    parts.append(f"on {s['date']}")
                if "time" in s:
                    time_str = s["time"]
                    if hasattr(time_str, 'strftime'):  # datetime.time object
                        time_str = time_str.strftime("%H:%M")
                    parts.append(f"at {time_str}")
                self.confirm_done = True
                self.logger.info("Asking detailed confirmation")
                return (
                        "Just to confirm: you want to travel "
                        + " ".join(parts) + ", correct?"
                )
            if "departure" not in s:
                return "(Info needed) Where are you departing from?"
            if "destination" not in s:
                return "(Info needed) Where are you going to?"

        # Prompt for missing slots
        if "date" not in s:
            return "(Info needed) On what date would you like to travel?"
        if "time" not in s:
            return "(Info needed) At what time would you prefer?"

        # Handle trip type determination
        if "trip_type" not in s:

            # Check if we already asked about return trip
            if "return_trip_asked" not in s:
                s["return_trip_asked"] = True
                return "(Info needed) Would you like to make it a return trip?"

            # Process the response
            if any(word in normalized_input for word in ["yes", "yeah", "yep", "sure", "return"]):
                s["trip_type"] = "return"
            elif any(word in normalized_input for word in
                     ["no", "nope", "single", "one way", "not a return", "just one way"]):
                s["trip_type"] = "single"
            else:
                return "(Info needed) Sorry, I didn't catch that. Is this a return trip? (yes/no)"

        # Handle passenger count, ASK ONLY ONCE
        if "passenger_count_asked" not in s:
            s["passenger_count_asked"] = True
            return "(Info needed) How many passengers will be travelling? (e.g., '1 adult', '2 adults and 1 child')"

        # Process passenger count response
        if "adults" not in s or "children" not in s:

            # Try to extract adult count
            adult_match = re.search(r"(\d+)\s*adult", normalized_input)
            adult_word_match = re.search(r"\b(one|two|three|four|five|six|seven|eight|nine)\s*adult", normalized_input)

            if adult_match:
                s["adults"] = int(adult_match.group(1))
            elif adult_word_match:
                num = self._word_to_number(adult_word_match.group(1))
                if num is not None:
                    s["adults"] = num
            elif re.search(r"\b(just me|only me|myself|one|1)\b", normalized_input) and "adult" not in normalized_input:
                s["adults"] = 1

            # Try to extract child count
            child_match = re.search(r"(\d+)\s*(child|children|kid)", normalized_input)
            child_word_match = re.search(r"\b(one|two|three|four|five|six|seven|eight|nine)\s*(child|children|kid)",
                                         normalized_input)

            if child_match:
                s["children"] = int(child_match.group(1))
            elif child_word_match:
                num = self._word_to_number(child_word_match.group(1))
                if num is not None:
                    s["children"] = num
            elif any(phrase in normalized_input for phrase in
                     ["no child", "no kid", "no children", "adult only", "adults only"]):
                s["children"] = 0

            # Set defaults if not explicitly mentioned
            if "adults" not in s:
                s["adults"] = 1  # Default to 1 adult if not specified
            if "children" not in s:
                s["children"] = 0  # Default to 0 children if not specified

            # If we still don't have both counts, ask for clarification
            if "adults" not in s or "children" not in s:
                return "(Info needed) Please specify the number of adults and children (e.g., '2 adults and 1 child' or 'just 1 adult')"

        # Handle return date and time for return trips
        if s.get("trip_type") == "return":
            if "return_date" not in s:
                return "(Info needed) What date would you like to return?"
            if "return_time" not in s:
                return "(Info needed) What time would you like to return?"

        # All slots present, perform ticket search
        dep = code_to_name[s["departure"]]
        dst = code_to_name[s["destination"]]

        # Normalize time to string format
        if hasattr(s["time"], 'strftime'):  # datetime.time object
            s["time"] = s["time"].strftime("%H:%M")

        #  Validate return date logic BEFORE submitting the ticket search
        if s.get("trip_type") == "return":
            try:
                dep_date = datetime.fromisoformat(s["date"])
                ret_date = datetime.fromisoformat(s["return_date"])
                if ret_date < dep_date:
                    return "⚠ Your return date is before your departure date. Please enter a valid return date."
            except Exception as e:
                self.logger.warning(f"Date parse error: {e}")

        self.logger.info(f"All slots filled: {s}, initiating ticket search")
        future = self.executor.submit(prepare_and_plan_journey, s)

        try:
            ticket = future.result(timeout=300)
        except TimeoutError:
            self.logger.error("Ticket search timed out")
            self._reset_state()
            return "Sorry, searching for tickets is taking too long. Please try again later."
        except Exception:
            self.logger.exception("Error during ticket search")
            self._reset_state()
            return "Oops, something went wrong fetching tickets. Try again later."

        # Present result, store last journey, then reset
        # Save last journey context for return-only queries later
        self.last_journey = {
            'departure': dep,
            'departure_code': s['departure'],
            'destination': dst,
            'destination_code': s['destination']
        }

        # Create a more informative response
        passenger_info = f"{s['adults']} adult{'s' if s['adults'] > 1 else ''}"
        if s['children'] > 0:
            passenger_info += f" and {s['children']} child{'ren' if s['children'] > 1 else ''}"

        trip_type_info = "return trip" if s.get("trip_type") == "return" else "single trip"

        resp = f"Found tickets for your {trip_type_info} ({passenger_info}). The cheapest fare is £{ticket.price:.2f}. Book here: {ticket.url}"
        self.logger.info("Presented cheapest ticket to user")
        self._reset_state()
        return resp

    # Predict train delay using collected slot data
    def _handle_predict_delay(self) -> str:
        s = self.state["slots"]

        # Required for this use-case
        required = ["rid", "station", "reported_delay", "destination"]
        missing = [slot for slot in required if slot not in s]
        if missing:
            return f"(Info needed) Please provide: {', '.join(missing)}."

        # Validate slot types
        try:
            rid = int(s["rid"])  # Ensure integer type
            station = s["station"]
            destination = s["destination"]
            reported_delay = float(s["reported_delay"])
            schedule = get_prediction_schedule(
                rid=rid,
                current_station=station,
                destination_station=destination
            )
            print("[DEBUG] Schedule received:", schedule)

            if schedule is None:
                return "Sorry, I couldn't find timetable info for that train and stations."

            # Safely parse date (handles both D/M/Y and Y-M-D formats)
            try:
                parsed_date = parse_service_date(schedule["date_of_service"])
                date_str = parsed_date.strftime("%d-%m-%Y")
            except ValueError as e:
                print(f"[ERROR] Failed to parse date: {e}")
                return "Sorry, there was an issue with the schedule date format."

            # Prepare the query for delay prediction
            query = {
                "rid": rid,
                "date_of_service": parsed_date,
                "station": destination,
                "reported_delay": reported_delay,
                "planned_arrival": schedule["planned_arrival"],
                "planned_departure": schedule["planned_departure"],
                "direction": schedule["direction"]
            }

            print(query)

            # Predict arrival time using the delay predictor
            result = predict_arrival_time(query)
            self._reset_state()
            return result

        # Handle errors during delay prediction
        except Exception as e:
            print("[ERROR] Exception caught in _handle_predict_delay:", repr(e))
            self.logger.exception("Delay prediction error")
            if 'query' in locals():
                print(f"[DEBUG] Query used in delay prediction: ")
            self._reset_state()
            return "Sorry, I couldn't calculate the arrival time right now."

# Instantiate the chatbot object
_bot = Chatbot()

# Get chatbot response for a message
def get_bot_response(msg: str) -> str:
    return _bot.respond(msg)

# Return current chatbot state as dict
def get_bot_state() -> dict:
    return {"intent": _bot.state.get("intent"),
            "slots": dict(_bot.state.get("slots", {})),
            "confirm_done": _bot.confirm_done}