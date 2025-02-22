import logging
import re
import time

import requests
from fake_useragent import UserAgent

from models import ApiKey


class ApiKeys:
    def __init__(self):
        self.api_keys = []
        self.load_keys()

    def add_key(self, key: ApiKey):
        self.api_keys.append(key)
        self.save_keys()

    def save_keys(self):
        with open("api_keys.txt", "w") as f:
            for key in self.api_keys:
                f.write(f"{key.key},{key.uses},{key.expires},{key.cap}\n")

    def load_keys(self):
        try:
            with open("api_keys.txt", "r") as f:
                for line in f:
                    key, uses, expires, cap = line.strip().split(",")
                    api_key = ApiKey(
                        key=key,
                        uses=0,
                        expires=int(expires),
                        cap=int(cap),
                        resetTime=0
                    )
                    self.add_key(api_key)
            self.clear_expired_keys()
        except FileNotFoundError:
            logging.warning("No API keys found. Generating a new one.")
            self.generate_key(force=True)

    def get_key(self):
        ### Gets the oldest key that has not expired and has not reached its cap
        ### adds 1 to the uses and returns the key. If resetTime is reached then reset uses before and set resetTime to current time + 1 min
        self.clear_expired_keys()
        for key in self.api_keys:

            if key.resetTime < int(time.time()):
                key.uses = 1
                key.resetTime = int(time.time()) + 60
                return key

            if key.uses < key.cap:
                key.uses += 1
                return key

    def clear_expired_keys(self):
        self.api_keys = [key for key in self.api_keys if key.expires > int(time.time())]

    def generate_key(self, force=False):
        if not force and self.api_keys and len(self.api_keys) > 1:
            return

        headers = {
            "User-Agent": UserAgent().google
        }
        logging.info("Generating API key...")
        response = requests.get("https://hardcover.app", headers=headers)

        try:
            response.raise_for_status()
        except requests.HTTPError:
            logging.error("Failed to generate API key.")

        stripped_data = response.text[(response.text.index(r'\"token\":\"') + 12):]

        index_1 = stripped_data.index(r'"])')
        index_2 = stripped_data.index(r'\",')

        if index_1 < index_2:
            stripped_data = stripped_data[:index_1]
        else:
            stripped_data = stripped_data[:index_2]

        api_key = ApiKey(
            key=stripped_data,
            uses=0,
            expires=int(time.time()) + 28 * 24 * 60 * 60,
            cap=80,
            resetTime=int(time.time()) + 60
        )

        self.add_key(api_key)

        print(f"Generated API key: {self.api_keys[-1].key}")
