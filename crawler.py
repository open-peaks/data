#!/usr/bin/env python3
import json
import os
import pprint
import re
import time
import urllib
from typing import Optional, List
from urllib.parse import urlencode

import pycountry
import pycountry_convert
import requests
from bs4 import BeautifulSoup
from geopy.geocoders import Nominatim
from pycountry_convert import country_alpha2_to_continent_code
from unidecode import unidecode


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


def get_peak_names():
    base_url = "https://en.wikipedia.org/wiki/Lists_of_mountains_by_region"
    for url in scrape_list_page(base_url):
        for peak_data in get_table_rows(url):
            name = peak_data.get("Mountain peak", "").split("[")[0]
            location = peak_data.get("Location", "")
            if not name or not location:
                continue
            yield name


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


class Peak:
    def __init__(self, name: str):
        self.name = name
        self.complete = False
        self.raw_coordinates = None
        self.prominence = None
        self.elevation = None
        self.parent_range = None
        self._parent_data = None
        self.location = None

    @property
    def url(self):
        clean_name = self.name.replace(" ", "_")
        return f"https://en.wikipedia.org/wiki/{clean_name}"

    @property
    def parent_range_url(self):
        if not self.parent_range:
            print("No parent range")
            return None
        clean_name = self.parent_range.replace(" ", "_")
        return f"https://en.wikipedia.org/wiki/{clean_name}"

    def flesh_out(self) -> bool:
        response = get_cache(self.url)
        if "Wikimedia list article" in response:
            return False
        if response is None:
            return False

        soup = BeautifulSoup(response, 'html.parser')
        tables = soup.find_all('table', class_="infobox")
        if len(tables) == 0:
            tables = soup.find_all('table')
        raw_text_data = {}
        for table in tables:
            for row in table.find_all('tr'):
                key_element = row.find('th')
                val_element = row.find('td')
                if key_element and val_element:
                    raw_text_data[key_element.text] = val_element.text
        if "Location" in raw_text_data:
            self.location = raw_text_data["Location"]

        for table in tables:
            for row in table.find_all('tr'):
                key_element = row.find('th', class_="infobox-label")
                val_element = row.find('td', class_="infobox-data")
                desired_keys = ["Elevation", "Prominence", "Parent range", "Isolation", "Coordinates", "Country", "Territory"]
                if key_element and val_element and key_element.text in desired_keys:
                    if key_element.text == "Coordinates":
                        val = val_element.find('span', class_="geo-dec").text
                        self.raw_coordinates = val

                    if key_element.text == "Elevation":
                        val = val_element.text.split(" (")[0].replace("\xa0", "").replace("+", "").strip()
                        self.elevation = val

                    if key_element.text == "Prominence":
                        val = val_element.text.split(" (")[0].replace("\xa0", "")
                        self.prominence = val

                    if key_element.text == "Country":
                        try:
                            val = val_element.find('a').text
                        except:
                            val = val_element.text
                            for bad_word in ["nuevo-león", "méxico", "veracruz"]:
                                if bad_word in val:
                                    val = val.replace(bad_word, "")
                        self.location = val

                    if key_element.text == "Parent range":
                        val = val_element.find('a').text
                        self.parent_range = val
                        data = self.flesh_out_parent_range()
                        if data:
                            self._parent_data = data
                            if "State" in data:
                                self.location = data["State"]
                                if self.location == "Hawaii":
                                    self.location = "Hawaii, United States"

        if self.location is None:
            geomap = soup.find_all('div', class_="locmap")
            if len(geomap) > 0:
                self.location = geomap[0].text.replace(self.name, "").split(" / ")[-1].strip()
                print("Found location from geomap: ", self.location)

        self.complete = True
        return True

    def flesh_out_parent_range(self) -> Optional[dict]:
        if not self.parent_range:
            return
        response = get_cache(self.parent_range_url)
        soup = BeautifulSoup(response, 'html.parser')
        tables = soup.find_all('table', class_="infobox")
        infobox_data = {}
        for table in tables:
            for row in table.find_all('tr'):
                key_element = row.find('th')
                val_element = row.find('td')
                if key_element and val_element:
                    infobox_data[key_element.text] = val_element.text
        return infobox_data

    @property
    def size(self):
        if not self.elevation:
            return None
        postfixes = ["ft", "m", "feet"]
        elevation = self.elevation
        for postfix in postfixes:
            if elevation.endswith(postfix):
                elevation = elevation.replace(postfix, "")
        elevation = elevation.replace(",", "")

        elevation = int(elevation.strip().split(".")[0])
        if elevation < 600:
            return "small"
        if elevation < 4200:
            return "medium"
        return "large"

    @property
    def coordinates(self):
        if not self.raw_coordinates:
            return None
        return extract_coordinates(self.raw_coordinates)

    @property
    def _latitude(self):
        if not self.coordinates:
            return None
        return self.coordinates[0]

    @property
    def _longitude(self):
        if not self.coordinates:
            return None
        return self.coordinates[1]

    @property
    def elevation_feet(self):
        if not self.elevation:
            return None
        elevation = self.elevation.replace(",", "")
        if elevation.endswith("ft"):
            elevation = elevation.replace("ft", "")
            elevation = float(elevation)
            return elevation

        if elevation.endswith("m"):
            elevation = elevation.replace("m", "")
            elevation = float(elevation)
            return elevation * 3.28084

    @property
    def _elevation_meters(self):
        if not self.elevation:
            return None
        elevation = self.elevation.replace(",", "")
        if elevation.endswith("ft"):
            elevation = elevation.replace("ft", "")
            elevation = float(elevation)
            return elevation / 3.28084

        if elevation.endswith("m"):
            elevation = elevation.replace("m", "")
            elevation = float(elevation)
            return elevation

    @property
    def _country(self):
        if not self.location:
            return None
        country_name = self.location.split(", ")[-1].strip().split("[")[0]
        if country_name.lower() in ["us", "u.s."]:
            country_name = "United States"
        return country_name

    def dict(self):
        return {
            "name": self.name,
            "url": self.url,
            "complete": self.complete,
            "raw_coordinates": self.raw_coordinates,
            "coordinates": self.coordinates,
            "elevation": self.elevation,
            "prominence": self.prominence,
            "parent_range": self.parent_range,
            "location": self.location,
            "size": self.size,
        }

    @property
    def _continent(self):
        if not self._country:
            return None
        country = self._country.split("[")[0]
        c = pycountry.countries.search_fuzzy(country)
        country_alpha2 = c[0].alpha_2
        continent_alpha2 = pycountry_convert.country_alpha2_to_continent_code(country_alpha2)
        continent_name = pycountry_convert.convert_continent_code_to_continent_name(continent_alpha2)
        return continent_name

    @property
    def geojson_filepath(self):
        current_dir = os.path.dirname(os.path.realpath(__file__))
        continent = self._continent.replace(" ", "-").lower()
        country = self._country.replace(" ", "-").lower()
        if country == "virgin-islands,-british":
            country = "british-virgin-islands"
        if continent == "oceania":
            continent = "australia-oceania"
        if country == "wyoming":
            country = "united-states"
        peak_name = unidecode(self.name.replace(" ", "-").lower())
        state = self._state

        path = f"{continent}/{country}/{peak_name}.geojson"
        if state and country not in ["canada", "mexico"]:
            state = state.replace(" ", "-").lower()
            path = f"{continent}/{country}/{state}/{peak_name}.geojson"

        return os.path.join(current_dir, path)

    @property
    def _state(self):
        if not self.location:
            return None
        parts = self.location.split(", ")
        if len(parts) == 3:
            return parts[1]

    @property
    def geojson(self):
        data = {
          "type": "Feature",
          "geometry": {
            "type": "Point",
            "coordinates": [
              self._longitude,
              self._latitude
            ]
          },
          "properties": {
            "feet": self.elevation_feet,
            "meters": self._elevation_meters,
            "latitude": self._latitude,
            "longitude": self._longitude,
            "name": self.name,
            "countries": [
                self._country,
            ],
            "continent": self._continent,
            "marker-size": self.size,
            "marker-symbol": "triangle"
          }
        }
        if self._state:
            data["properties"]["states"] = [self._state]
        return data

    def save(self):
        filepath = self.geojson_filepath
        dir_name = os.path.dirname(filepath)
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)

        with open(filepath, "w") as f:
            json.dump(self.geojson, f, indent=4)


if __name__ == "__main__":
    peak_count = 0
    for name in get_peak_names():
        peak_count += 1
        peak = Peak(name)
        success = peak.flesh_out()
        if not success:
            print(f"Failed to flesh out {name}")
            continue

        try:
            print(f"{peak_count}\tSaving {name}")
            peak.save()
        except Exception as e:
            print(f"Failed to save {name} because {e}")
