"""Launch the App with the local test service; importing has no side effects."""

import time

# isort: split
# --8<-- [start:open]
from typing import Literal

from cuiman import Client
from cuiman.app import App


def open_app(display: Literal["browser", "notebook"] = "browser") -> tuple[Client, App]:
    """Open the App and return the client and server handles for later cleanup."""
    client = Client(api_url="http://127.0.0.1:8008", auth={"auth_type": "none"})
    try:
        app = client.show_app(display=display, height=640)
    except Exception:
        client.close()
        raise
    return client, app


# --8<-- [end:open]


# --8<-- [start:request]
def set_duration(app: App, duration: float = 2) -> None:
    """Update the sleep form without replacing its other inputs or outputs."""
    request = app.get_process_request("sleep_a_while")
    if request is None:
        raise ValueError("Open the sleep_a_while process in the App first.")
    if request.inputs is None:
        request.inputs = {}
    request.inputs["duration"] = duration
    app.set_process_request("sleep_a_while", request)


# --8<-- [end:request]


# --8<-- [start:close]
def close_app(client: Client, app: App) -> None:
    """Stop the App server and close the client even if stopping fails."""
    try:
        app.serve_result.stop()
    finally:
        client.close()


# --8<-- [end:close]


def main() -> None:
    """Keep a browser App alive until Ctrl+C, then release its resources."""
    client, app = open_app()
    try:
        print("App is running. Press Ctrl+C to stop.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        close_app(client, app)


if __name__ == "__main__":
    main()
