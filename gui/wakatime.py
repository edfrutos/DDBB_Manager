import base64
import json
import os
import threading
import time
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen


class WakaTimeTracker:
    """Envía heartbeats opcionales a WakaTime cuando se configura una API key."""

    def __init__(self, api_key, project_name="DDBB_Manager", enabled=True, timeout=5.0):
        self.api_key = api_key.strip()
        self.project_name = project_name.strip() or "DDBB_Manager"
        self.enabled = enabled
        self.timeout = timeout

    @classmethod
    def from_environment(cls):
        enabled = os.environ.get("WAKATIME_ENABLED", "false").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        api_key = os.environ.get("WAKATIME_API_KEY", "").strip()
        if not enabled or not api_key:
            return None
        project_name = os.environ.get("WAKATIME_PROJECT_NAME", "DDBB_Manager").strip()
        return cls(api_key=api_key, project_name=project_name or "DDBB_Manager")

    def build_payload(self, entity, category="manual testing", type_="app", timestamp=None):
        return {
            "entity": entity,
            "type": type_,
            "category": category,
            "time": float(timestamp if timestamp is not None else time.time()),
            "project": self.project_name,
        }

    def heartbeat(self, entity, category="manual testing", type_="app", sync=False):
        if not self.enabled or not self.api_key:
            return False

        payload = self.build_payload(entity, category=category, type_=type_)

        if sync:
            return self._post_payload(payload)

        thread = threading.Thread(target=self._post_payload, args=(payload,), daemon=True)
        thread.start()
        return True

    def _post_payload(self, payload):
        data = json.dumps(payload).encode("utf-8")
        auth = base64.b64encode(f"{self.api_key}:".encode("utf-8")).decode("ascii")

        request = Request(
            "https://api.wakatime.com/api/v1/users/current/heartbeats",
            data=data,
            method="POST",
            headers={
                "Authorization": f"Basic {auth}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": f"DDBB_Manager/1.0.0",
            },
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                return response.status in {200, 201, 202}
        except (HTTPError, URLError, TimeoutError, ValueError):
            return False
        except Exception:
            return False
