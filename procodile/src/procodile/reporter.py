#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import json
import logging
import threading
from typing import Any
from urllib import error, request

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_Payload = tuple[str, dict[str, Any]]


class CallbackReporter:
    def __init__(
        self,
        request_timeout: float = 1.0,
        check_interval: float = 0.5,
    ):
        self.request_timeout = request_timeout
        self.check_interval = check_interval
        self._latest_payload: _Payload | None = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._notify_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def report(self, url: str, data: dict[str, Any]):
        with self._lock:
            self._latest_payload = url, data
        self._notify_event.set()

    def stop(self):
        self._stop_event.set()
        self._thread.join(timeout=2.0)

    def _run(self):
        while not self._stop_event.is_set():
            triggered = self._notify_event.wait(timeout=self.check_interval)
            if triggered:
                self._notify_event.clear()
                with self._lock:
                    payload = self._latest_payload
                if payload:
                    try:
                        self._post_json(payload)
                        logger.info(f"Successfully posted status to {payload[0]}")
                    except (error.URLError, error.HTTPError) as e:
                        logger.warning("Post failed: %s", e)
                    except Exception as e:
                        logger.exception("Unexpected error in reporter: %s", e)

    def _post_json(self, payload: tuple[str, dict]):
        url, data = payload
        json_text = json.dumps(data).encode("utf-8")
        req = request.Request(
            url,
            data=json_text,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=self.request_timeout) as resp:
            resp.read()
