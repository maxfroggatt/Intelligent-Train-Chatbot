import base64
import requests

# HSP API client with base URL
class HSPClient:
    BASE_URL = "https://hsp-prod.rockshore.net/api/v1/"

    # Set up basic auth headers
    def __init__(self, email: str, password: str):
        creds = f"{email}:{password}".encode()
        self.headers = {
            "Authorization": "Basic " + base64.b64encode(creds).decode(),
            "Content-Type": "application/json"
        }

    # Build payload for service metrics request
    def get_service_metrics(self,
                            from_loc: str, to_loc: str,
                            from_time: str, to_time: str,
                            from_date: str, to_date: str,
                            days: str = "WEEKDAY",
                            toc_filter: list[str] = None,
                            tolerance: list[str] = None):
        payload = {
            "from_loc": from_loc,
            "to_loc": to_loc,
            "from_time": from_time,
            "to_time": to_time,
            "from_date": from_date,
            "to_date": to_date,
            "days": days
        }

        # Send metrics request and return services
        if toc_filter:  payload["toc_filter"] = toc_filter
        if tolerance:   payload["tolerance"] = tolerance
        resp = requests.post(self.BASE_URL + "serviceMetrics", headers=self.headers, json=payload)
        resp.raise_for_status()
        return resp.json()["Services"]

    # Fetch detailed info for a service
    def get_service_details(self, rid: str):
        payload = {"rid": rid}
        resp = requests.post(self.BASE_URL + "serviceDetails",
                             headers=self.headers, json=payload)
        resp.raise_for_status()
        return resp.json()["serviceAttributesDetails"]