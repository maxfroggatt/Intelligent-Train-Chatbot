import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import os
import time
import sqlite3
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from services.darwin import list_available_file_versions, parse_journey_file

# Absolute path to DB
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DB_PATH = os.path.join(BASE_DIR, 'database', 'train_data.db')

# Save journey details to the database
def plan_journey_with_cheapest_ticket(origin, destination, dep_date, dep_hour, dep_min, return_date, return_hour, return_min, adults, children, is_return):
    # Record journey query in DB
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO journey_queries (
            user_input, origin, destination,
            departure_date, return_date,
            departure_time, return_time,
            adults, children, is_return
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        f"{origin} to {destination} on {dep_date} at {dep_hour}:{dep_min}",
        origin, destination, dep_date, return_date,
        f"{dep_hour}:{dep_min}", f"{return_hour}:{return_min}",
        int(adults), int(children), is_return
    ))
    conn.commit()
    conn.close()

    # DARWIN matching
    matched_journeys = []
    journey_summary = ""
    files = list_available_file_versions()

    # Parse latest Darwin timetable file
    if files:
        latest_file = files[max(files)]
        print(f"[DARWIN] Using file: {latest_file}")
        matched_journeys = parse_journey_file(
            file_key=latest_file,
            origin_crs=origin,
            dest_crs=destination,
            latest_dep_time=f"{dep_hour}:{dep_min}"
        )

        # Store matched journeys in the database
        if matched_journeys:
            print(f"[DARWIN] Found {len(matched_journeys)} journeys.")
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(id) FROM journey_queries")
            journey_query_id = cursor.fetchone()[0]
            seen = set()

            # Insert unique journey matches into DB
            for match in matched_journeys:
                key = (match['departure_time'], match['arrival_time'])
                if key not in seen:
                    seen.add(key)
                    cursor.execute('''
                        INSERT INTO darwin_journeys (
                            journey_query_id, origin, destination, departure_time, tiploc_route, matched
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        journey_query_id,
                        match['origin'],
                        match['destination'],
                        match['departure_time'],
                        ','.join(match['tiploc_route']),
                        True
                    ))
            conn.commit()
            conn.close()

            # Format top 5
            journey_summary = "\n".join([
                f"- {j['departure_time']} → {j['arrival_time']} | {' → '.join(j['station_route'])}"
                for j in sorted(matched_journeys, key=lambda x: x['departure_time'])[:5]
            ])
        else:
            print("[DARWIN] No valid journeys found.")
            journey_summary = "(No valid journeys in Darwin timetable)"
    else:
        print("[DARWIN] No timetable files available.")
        journey_summary = "(No Darwin timetable files found)"

    # Web scraping via Selenium
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-dev-shm-usage")

    # Launch headless Chrome with wait handler
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    wait = WebDriverWait(driver, 30)

    cheapest_price = None
    booking_url = ""

    # Fill journey form, submit, and scrape prices
    try:
        driver.get("https://www.nationalrail.co.uk/")
        try:
            # Accept cookies popup
            wait.until(EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))).click()
        except:
            pass

        # Click 'Plan Your Journey' button
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[aria-label='Plan Your Journey']"))).click()

        # Enter origin and destination stations
        wait.until(EC.element_to_be_clickable((By.ID, "jp-origin"))).send_keys(origin)
        wait.until(EC.element_to_be_clickable((By.ID, "jp-destination"))).send_keys(destination)

        # Clear and enter departure date
        dep_input = wait.until(EC.element_to_be_clickable((By.ID, "leaving-date")))
        dep_input.click()
        dep_input.send_keys(Keys.CONTROL + "a", Keys.BACKSPACE)
        dep_input.send_keys(dep_date)
        time.sleep(0.3)

        # Set departure time and type
        wait.until(EC.visibility_of_element_located((By.XPATH, "//button[contains(., 'Get times and prices')]")))
        Select(driver.find_element(By.ID, "leaving-type")).select_by_value("departing")
        Select(driver.find_element(By.ID, "leaving-hour")).select_by_value(dep_hour)
        Select(driver.find_element(By.ID, "leaving-min")).select_by_value(dep_min)

        # Fill in return trip details if selected
        if is_return:
            wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "label[for='radio-jp-ticket-type-return']"))).click()
            ret_input = wait.until(EC.element_to_be_clickable((By.ID, "return-date")))
            ret_input.click()
            ret_input.send_keys(Keys.CONTROL + "a", Keys.BACKSPACE)
            ret_input.send_keys(return_date)
            time.sleep(0.3)

            # Set return time and type
            Select(driver.find_element(By.ID, "return-type")).select_by_value("departing")
            Select(driver.find_element(By.ID, "return-hour")).select_by_value(return_hour)
            Select(driver.find_element(By.ID, "return-min")).select_by_value(return_min)

        # Select number of adult and children tickets
        Select(driver.find_element(By.ID, "adults")).select_by_value(str(adults))
        Select(driver.find_element(By.ID, "children")).select_by_value(str(children))

        # Submit journey search and wait
        wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Get times and prices')]"))).click()
        print("Journey submitted.")
        time.sleep(5)

        # Get and print booking page URL
        booking_url = driver.current_url
        print(f"Booking page URL: {booking_url}")

        price_elements = driver.find_elements(By.XPATH, "//*[contains(text(), '£')]")
        prices = []

        # Extract and filter valid price values
        for el in price_elements:
            try:
                text = el.text.strip()
                if "£" in text:
                    price = float(text.split("£")[1].split()[0].replace(",", ""))
                    if price >= 1.00:
                        prices.append(price)
            except:
                continue

        # Find and display the lowest valid price
        if prices:
            cheapest_price = min(prices)
            print(f"Cheapest price: £{cheapest_price:.2f}")
        else:
            print("No valid prices found.")

    finally:
        driver.quit()

    # Save ticket result to the database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO ticket_results (
            origin, destination, is_return, departure_date, return_date,
            cheapest_price, booking_url
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        origin, destination, is_return, dep_date, return_date,
        cheapest_price, booking_url
    ))
    conn.commit()
    conn.close()

    # Format final message with journey and price info
    message = (
        f"We found {len(matched_journeys)} valid journeys from {origin} to {destination}.\n"
        f"{journey_summary}\n\n"
        f"The cheapest {'return' if is_return else 'single'} is £{cheapest_price:.2f}.\nBook here: {booking_url}"
    ) if cheapest_price else "No tickets found."

    # Return journey result as a dictionary
    return {
        "origin": origin,
        "destination": destination,
        "is_return": is_return,
        "departure_date": dep_date,
        "return_date": return_date,
        "cheapest_price": cheapest_price,
        "booking_url": booking_url,
        "journey_options": journey_summary,
        "message": message
    }

# Test with sample input
if __name__ == "__main__":
    plan_journey_with_cheapest_ticket(
        origin="NRW",
        destination="LST",
        dep_date="25 Jul 2025",
        dep_hour="10",
        dep_min="15",
        return_date="28 Jul 2025",
        return_hour="12",
        return_min="30",
        adults="2",
        children="1",
        is_return=True
    )