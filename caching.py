# file: caching.py
import os
import hashlib
import json
from collections import OrderedDict
from typing import Optional

MEMORY_CACHE_LIMIT = 10 * 1024 * 1024
FILE_CACHE_LIMIT = 1 * 1024 * 1024 * 1024
FILE_CACHE_DIR = "file_cache"
MEMORY_CACHE = OrderedDict()  # { cache_key: (size_in_bytes, response_bytes) }

if not os.path.exists(FILE_CACHE_DIR):
    os.makedirs(FILE_CACHE_DIR)


def get_cache_key(query: str, author: str, lang: Optional[str], retype: Optional[str]) -> str:
    raw_key = f"{query}-{author}-{lang}-{retype}"
    return hashlib.md5(raw_key.encode("utf-8")).hexdigest()


def calculate_size_in_bytes(data: bytes) -> int:
    return len(data)


def enforce_file_limit():
    file_entries = sorted(
        [
            (f, os.path.getsize(os.path.join(FILE_CACHE_DIR, f)))
            for f in os.listdir(FILE_CACHE_DIR)
        ],
        key=lambda x: os.path.getmtime(os.path.join(FILE_CACHE_DIR, x))
    )
    total_size = sum(x[1] for x in file_entries)
    while total_size > FILE_CACHE_LIMIT and file_entries:
        oldest_file, size = file_entries.pop(0)
        os.remove(os.path.join(FILE_CACHE_DIR, oldest_file))
        total_size -= size


def store_in_file(cache_key: str, data: bytes):
    file_path = os.path.join(FILE_CACHE_DIR, cache_key + ".json")
    with open(file_path, "wb") as f:
        f.write(data)
    enforce_file_limit()


def enforce_memory_limit():
    global MEMORY_CACHE
    current_size = sum(x[0] for x in MEMORY_CACHE.values())
    while current_size > MEMORY_CACHE_LIMIT and MEMORY_CACHE:
        # Move the oldest item to the file cache
        oldest_key, oldest_value = MEMORY_CACHE.popitem(last=False)
        store_in_file(oldest_key, oldest_value[1])
        current_size = sum(x[0] for x in MEMORY_CACHE.values())


def store_in_memory(cache_key: str, data: bytes):
    global MEMORY_CACHE
    if cache_key in MEMORY_CACHE:
        del MEMORY_CACHE[cache_key]
    MEMORY_CACHE[cache_key] = (calculate_size_in_bytes(data), data)
    enforce_memory_limit()


def get_from_memory(cache_key: str):
    global MEMORY_CACHE
    if cache_key in MEMORY_CACHE:
        size, content = MEMORY_CACHE[cache_key]
        # Reinsert to keep it as the newest
        del MEMORY_CACHE[cache_key]
        MEMORY_CACHE[cache_key] = (size, content)
        return content
    return None


def get_from_file(cache_key: str):
    file_path = os.path.join(FILE_CACHE_DIR, cache_key + ".json")
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            content = f.read()
        # Store it in memory
        store_in_memory(cache_key, content)
        return content
    return None
