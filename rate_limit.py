# file: rate_limit.py
import time
from fastapi import HTTPException
from typing import Dict, List

# This stores the timestamps of requests for each IP
# { ip: [timestamps_in_seconds] }
REQUEST_LOG: Dict[str, List[float]] = {}

limit = 15


def rate_limit_check(ip: str):
    now = time.time()
    timestamps = REQUEST_LOG.get(ip, [])
    one_minute_ago = now - 60
    # keep only the last minute's requests
    timestamps = [t for t in timestamps if t > one_minute_ago]
    if len(timestamps) >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded ({limit} requests per minute). Please try again later."
        )
    timestamps.append(now)
    REQUEST_LOG[ip] = timestamps


def clear_old_ips():
    """
    Remove IPs that have not had a request in the last minute.
    This can be called periodically (e.g., every hour).
    """
    now = time.time()
    one_minute_ago = now - 60
    for ip, timestamps in list(REQUEST_LOG.items()):
        # If all timestamps are older than 1 minute, remove them
        if all(t < one_minute_ago for t in timestamps):
            del REQUEST_LOG[ip]
