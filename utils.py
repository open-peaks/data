#!/usr/bin/env python3
import os
import re
import time
import urllib
from typing import Optional
from urllib.parse import urlencode

import requests
from unidecode import unidecode

def extract_coordinates(input_string):
    s = input_string.replace("°", "")
    parts = s.split(" ")
    if len(parts) == 2:
        latitude = parts[0]
        if latitude.endswith("S"):
            latitude = "-" + latitude.replace("S", "")
        else:
            latitude = latitude.replace("N", "")

        longitude = parts[1]
        if longitude.endswith("W"):
            longitude = "-" + longitude.replace("W", "")
        else:
            longitude = longitude.replace("E", "")

        latitude = float(latitude)
        longitude = float(longitude)
        return latitude, longitude

    # Define a regular expression pattern to match latitude and longitude
    pattern = r'(\d+)°(\d+)′(\d+)″([NS]) (\d+)°(\d+)′(\d+)″([EW])'

    # Search for the pattern in the input string
    match = re.search(pattern, input_string)

    if not match:
        return None, None

    # Extract degrees, minutes, seconds, and direction for latitude and longitude
    lat_deg, lat_min, lat_sec, lat_dir, lon_deg, lon_min, lon_sec, lon_dir = match.groups()

    # Convert to decimal degrees
    latitude = float(lat_deg) + float(lat_min) / 60 + float(lat_sec) / 3600
    if lat_dir == 'S':
        latitude = -latitude

    longitude = float(lon_deg) + float(lon_min) / 60 + float(lon_sec) / 3600
    if lon_dir == 'W':
        longitude = -longitude

    return latitude, longitude


def get_cache(url: str) -> Optional[str]:
    filename = url.replace("https://", "")
    cached_filepath = f"cache/{filename}.html"
    if os.path.exists(cached_filepath):
        with open(cached_filepath, 'r') as f:
            content = f.read()
            if content == "redirect":
                return None
            return content

    # Add a delay to avoid overloading the server
    time.sleep(2)

    path = os.path.dirname(cached_filepath)
    if not os.path.exists(path):
        os.makedirs(path)

    response = requests.get(url)
    ok_redirects = [
      unidecode(url),
        urllib.parse.quote(url).replace("https%3A//", "https://"),
    ]
    if response.url != url and response.url not in ok_redirects:
        with open(cached_filepath, 'w') as f:
            print(f"Redirected from {url} to {response.url}, and it's not a known redirect ({ok_redirects})")
            f.write("redirect")
        return None

    with open(cached_filepath, 'w') as f:
        f.write(response.text)
    return response.text

