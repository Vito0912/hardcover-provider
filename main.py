# file: main.py
import uvicorn
from app import create_app
from rate_limit import clear_old_ips
import threading
import time
import logging
import dotenv

from retreive_api_keys import ApiKeys

logger = logging.getLogger("uvicorn")

app = create_app()
api_keys = ApiKeys()

def hourly_cleanup():
    """
    A simple background thread to run clear_old_ips every hour.
    """
    while True:
        clear_old_ips()
        logger.info("Cleared old IPs from rate limit store.")
        time.sleep(3600)  # 1 hour


if __name__ == "__main__":
    # Start the background cleanup thread
    cleanup_thread = threading.Thread(target=hourly_cleanup, daemon=True)
    cleanup_thread.start()

    api_keys.generate_key()

    uvicorn.run(app, host="0.0.0.0", port=7790)
