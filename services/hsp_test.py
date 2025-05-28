import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from services.hsp_client import HSPClient

if __name__ == "__main__":
    # Initialize HSP client with credentials
    hsp = HSPClient(email="christiancab101@gmail.com",
                    password="sLW6d9p9U7!!Ux7")

    # Fetch and print service metrics
    services = hsp.get_service_metrics(
        from_loc="BTN",
        to_loc="VIC",
        from_time="0700",
        to_time="0800",
        from_date="2025-05-01",
        to_date="2025-05-01",
        days="WEEKDAY",
        tolerance=["5"]
    )
    print("SERVICE METRICS:\n", services)

    # Get and print details for first service
    if services:
        first_rid = services[0]["serviceAttributesMetrics"]["rids"][0]
        details = hsp.get_service_details(first_rid)
        print("\nSERVICE DETAILS for", first_rid, ":\n", details)
    else:
        print("No services returned for that query.")