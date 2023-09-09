#!/usr/bin/env python3
import json
import os
import re
import time

import pycountry
import pycountry_convert
import requests
from bs4 import BeautifulSoup
from geopy.geocoders import Nominatim
from pycountry_convert import country_alpha2_to_continent_code
from unidecode import unidecode


def get_cache(url: str) -> str:
    filename = url.replace("https://", "")
    cached_filepath = f"cache/{filename}.html"
    if os.path.exists(cached_filepath):
        with open(cached_filepath, 'r') as f:
            return f.read()

    # Add a delay to avoid overloading the server
    time.sleep(2)

    path = os.path.dirname(cached_filepath)
    if not os.path.exists(path):
        os.makedirs(path)

    response = requests.get(url)
    with open(cached_filepath, 'w') as f:
        f.write(response.text)
    return response.text


def get_list_page_links(url: str) -> list[str]:
    page_links = []
    response = get_cache(url)
    soup = BeautifulSoup(response, 'html.parser')
    for link in soup.find_all('a'):
        href = link.get('href')
        if href and "/wiki/List_of_mountain_peaks" in href:
            page_links.append(f"https://en.wikipedia.org{href}")
    return page_links


def scrape_list_page(starting_url):
    visited_urls = set()
    queue = [starting_url]
    while queue:
        print("visited", len(visited_urls), "queue", len(queue))
        url = queue.pop(0)
        if url in visited_urls:
            continue
        visited_urls.add(url)
        page_links = get_list_page_links(url)
        for link in page_links:
            if "List_of_mountain_peaks" in link:
                queue.append(link)
            yield link


def get_peaks():
    base_url = "https://en.wikipedia.org/wiki/Lists_of_mountains_by_region"
    for url in scrape_list_page(base_url):
        for peak_data in get_table_rows(url):
            name = peak_data.get("Mountain peak", "").split("[")[0]
            location = peak_data.get("Location", "")
            if not name or not location:
                continue
            yield name, location


def get_table_rows(wikipedia_url):
    response = get_cache(wikipedia_url)
    soup = BeautifulSoup(response, 'html.parser')
    tables = soup.find_all('table')

    table = None
    for table in tables:
        if len(table.find_all("th")) == 0:
            continue

        # Extract data from the table (modify this part according to your specific needs)
        headers = []
        for th in table.find_all("th"):
            headers.append(th.text.strip())

        for row in table.find_all('tr'):
            row_data = [cell.text.strip() for cell in row.find_all('td')]

            if len(row_data) != len(headers):
                continue

            dict_data = {}
            for i in range(len(row_data)):
                key = headers[i]
                val = row_data[i]
                dict_data[key] = val
            yield dict_data


def get_cached_address_data(latitude, longitude):
    filename = f"./cache/nominatim/{latitude}_{longitude}.json"
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            return json.load(f)

    time.sleep(2)
    geolocator = Nominatim(user_agent="location_metadata_app")
    data = geolocator.reverse((latitude, longitude), exactly_one=True)
    address = data.raw

    path = os.path.dirname(filename)
    if not os.path.exists(path):
        os.makedirs(path)
    with open(filename, 'w') as f:
        json.dump(address, f, indent=4)
    return address


def get_metadata(latitude, longitude, name):
    address = get_cached_address_data(latitude, longitude)
    alpha2_code = address["address"]["country_code"].upper()

    continent_code = country_alpha2_to_continent_code(alpha2_code)
    continent_name = pycountry_convert.convert_continent_code_to_continent_name(continent_code)
    continent_name = continent_name
    country_name = pycountry.countries.get(alpha_2=alpha2_code).name

    latitude = round(latitude, 4)
    longitude = round(longitude, 4)

    peak = {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [
                longitude,
                latitude
            ]
        },
        "properties": {
            "feet": None,
            "meters": None,
            "latitude": latitude,
            "longitude": longitude,
            "name": name,
            "regions": [],
            "countries": [country_name],
            "continent": continent_name,
            "marker-size": "large",
            "marker-symbol": "triangle"
        }
    }

    if address["address"]["country"] == "United States":
        peak["properties"]["states"] = [address["address"]["state"]]
        if peak["properties"]["states"] == ["Hawaii"]:
            peak["properties"]["continent"] = "australia-oceania"

    return peak


def extract_coordinates(input_string):
    # Define a regular expression pattern to match latitude and longitude
    pattern = r'(\d+)°(\d+)′(\d+)″([NS]) (\d+)°(\d+)′(\d+)″([EW])'

    # Search for the pattern in the input string
    match = re.search(pattern, input_string)

    if match:
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
    else:
        return None


def get_filepath(peak):
    continent = peak["properties"]["continent"].replace(" ", "-").lower()
    country = peak["properties"]["countries"][0].replace(" ", "-").lower()
    peak_name = unidecode(peak["properties"]["name"].replace(" ", "-").lower())
    state = peak["properties"].get("state")
    if country == "virgin-islands,-british":
        country = "british-virgin-islands"
    if state:
        state = state.replace(" ", "-").lower()
        return f"{continent}/{country}/{state}/{peak_name}.geojson"

    return f"{continent}/{country}/{peak_name}.geojson"


if __name__ == "__main__":
    peak_count = 0
    for name, location in get_peaks():
        peak_count += 1
        lat, lng = extract_coordinates(location)
        peak = get_metadata(lat, lng, name)
        filepath = get_filepath(peak)

        dir_name = os.path.dirname(filepath)
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)

        print(peak_count, filepath)
        with open(filepath, "w") as f:
            json.dump(peak, f, indent=4)
