import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

# Enter origin station
def select_origin_and_destination(driver, origin, destination):
    wait = WebDriverWait(driver, 20)

    # Origin input
    origin_trigger = wait.until(EC.element_to_be_clickable((By.ID, "jsf-origin-input")))
    origin_trigger.click()
    print("Clicked origin input")

    # Wait for the input to be ready
    origin_input = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[data-testid='jsf-origin']")))
    origin_input.clear()
    origin_input.send_keys(origin)
    print("Typed origin: {origin}")
    time.sleep(1.5)
    origin_input.send_keys(Keys.RETURN)
    time.sleep(1)

    # Verify selected origin
    selected_origin = driver.find_element(By.ID, "jsf-origin-input").get_attribute("value")
    if origin.lower() in selected_origin.lower():
        print("Origin confirmed: {selected_origin}")
    else:
        print("Origin mismatch: Got '{selected_origin}', expected '{origin}'")

    # Desination input
    dest_trigger = wait.until(EC.element_to_be_clickable((By.ID, "jsf-destination-input")))
    dest_trigger.click()
    print("Clicked destination input")

    # Wait for the input to be ready
    dest_input = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[data-testid='jsf-destination']")))
    dest_input.clear()
    dest_input.send_keys(destination)
    print("Typed destination: {destination}")
    time.sleep(1.5)
    dest_input.send_keys(Keys.RETURN)
    time.sleep(1)

    # Verify selected destination
    selected_dest = driver.find_element(By.ID, "jsf-destination-input").get_attribute("value")
    if destination.lower() in selected_dest.lower():
        print("Destination confirmed: {selected_dest}")
    else:
        print("Destination mismatch: Got '{selected_dest}', expected '{destination}'")

# Select date and time from calendar
def select_date_and_time(driver, field_id, target_month, target_day, hour_val, minute_val):
    wait = WebDriverWait(driver, 15)
    print("Looking for: {target_month} {target_day}")

    # Open calendar
    field = wait.until(EC.element_to_be_clickable((By.ID, field_id)))
    driver.execute_script("arguments[0].click();", field)

    # Navigate calendar
    for _ in range(12):
        month_label = driver.find_element(By.ID, "datetime-picker-label").text.strip()

        # Check if the current month matches the target month
        if month_label == target_month:
            try:
                day_button = driver.find_element(By.CSS_SELECTOR,
                    f'button[data-testid="jsf-calendar-date-button-{target_day}"]')
                driver.execute_script("arguments[0].scrollIntoView(true);", day_button)
                day_button.click()
                print("Selected: {target_month} {target_day}")

                time.sleep(1)

                # Select hour and minute
                Select(driver.find_element(By.ID, "jsf-outbound-time-time-picker-hour")).select_by_value(hour_val)
                Select(driver.find_element(By.ID, "jsf-outbound-time-time-picker")).select_by_value(minute_val)
                print("Time set to {hour_val}:{minute_val}")
                return {"status": f"Selected {target_month} {target_day} {hour_val}:{minute_val}"}
            except Exception as e:
                print("Could not click day {target_day} or select time:", e)
                return {"error": f"Could not complete selection for {target_day}"}
        else:
            driver.find_element(By.CSS_SELECTOR, 'button[data-testid="calendar-navigate-to-next-month"]').click()
            time.sleep(0.8)

    return {"error": "Could not reach {target_month}"}

# Run the scraper
if __name__ == "__main__":
    options = webdriver.ChromeOptions()
    options.add_argument("--window-size=1920,1080")
    driver = webdriver.Chrome(options=options)

    try:
        driver.get("https://www.thetrainline.com")
        print("Opened Trainline")
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        # Accept cookies
        try:
            WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))
            ).click()
            print("Cookie banner closed")
        except:
            print("No cookie banner")

        # Select stations
        select_origin_and_destination(driver, "Norwich", "London Liverpool Street")

        # Select date and time
        result = select_date_and_time(
            driver,
            field_id="jsf-outbound-time-input-toggle",
            target_month="August 2025",
            target_day="20",
            hour_val="18",
            minute_val="15"
        )

        # Dismiss calendar
        try:
            body = driver.find_element(By.TAG_NAME, "body")
            body.click()
            time.sleep(1)
        except Exception as e:
            print("Could not dismiss calendar:", e)

        # Click 'Get cheapest tickets'
        search_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[data-testid="jsf-submit"]'))
        )
        search_button.click()
        print("Clicked 'Get cheapest tickets'")

        # Wait for results
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='outbound-journey']"))
        )
        print("Results page loaded")
        print("Final result:", result)
        input("Press Enter to close browser...")

    finally:
        driver.quit()