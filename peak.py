#!/usr/bin/env python3
import json
import os
import pprint
from typing import Optional

import pycountry
import pycountry_convert
from bs4 import BeautifulSoup
from unidecode import unidecode

from utils import get_cache, extract_coordinates


class Peak:
    def __init__(self, name: str, url: str):
        self.name = name
        self.url = url
        self.complete = False
        self.raw_coordinates = None
        self.prominence = None
        self.elevation = None
        self.parent_range = None
        self._parent_data = None
        self.location = None
        self.__continent = None

    def __repr__(self):
        continent = self._continent.ljust(15, ' ')
        country = self._country.ljust(20, ' ')
        name = self.name.ljust(50, ' ')
        return f"{continent}{country}{name}{self.url}"
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

        if "(" in self.name:
            self.name = self.name.split("(")[0].replace("_", " ").strip()


        for table in tables:
            for row in table.find_all('tr'):
                key_element = row.find('th', class_="infobox-label")
                val_element = row.find('td', class_="infobox-data")
                desired_keys = ["Elevation", "Prominence", "Parent range", "Isolation", "Coordinates", "Country", "Territory"]
                if key_element and val_element and key_element.text in desired_keys:
                    if key_element.text == "Coordinates":
                        try:
                            val = val_element.find('span', class_="geo-dec").text
                        except:
                            val = val_element.text
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
                        a = val_element.find('a')
                        if a:
                            val = a.text
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
                if "Show map of " in self.location:
                    self.location = self.location.split("Show map of ")[0].strip()

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
            elevation = float(elevation.split("[")[0])
            return elevation

        if elevation.endswith("m"):
            elevation = elevation.replace("m", "")
            elevation = float(elevation.split("[")[0])
            return elevation * 3.28084

    @property
    def _elevation_meters(self):
        if not self.elevation:
            return None
        elevation = self.elevation.replace(",", "")
        if elevation.endswith("ft"):
            elevation = elevation.replace("ft", "")
            elevation = float(elevation.split("[")[0])
            return elevation / 3.28084

        if elevation.endswith("m"):
            elevation = elevation.replace("m", "")
            elevation = float(elevation.split("[")[0])
            return elevation

    @property
    def _country(self):
        if not self.location:
            return None
        country_name = self.location.split(", ")[-1].strip().split("[")[0].split("(")[0].split(" and ")[0].strip()
        for s in ["inland", "Inland", "northern", "Northern"]:
            if s in country_name:
                country_name = country_name.replace(s, "")
        mappings = {
            "england": "United Kingdom",
            "us": "United States",
            "u.s.": "United States",
        }
        if country_name.lower() in mappings:
            country_name = mappings[country_name.lower()]
        c = pycountry.countries.search_fuzzy(country_name)
        country_name = c[0].name

        # calculate continent
        country_alpha2 = c[0].alpha_2
        continent_alpha2 = pycountry_convert.country_alpha2_to_continent_code(country_alpha2)
        self.__continent = pycountry_convert.convert_continent_code_to_continent_name(continent_alpha2)

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
        if self.__continent is not None:
            return self.__continent
        self._country
        return self.__continent

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
        if state and country in ["united-states"]:
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
        if not self.complete:
            self.flesh_out()

        filepath = self.geojson_filepath
        dir_name = os.path.dirname(filepath)
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)

        with open(filepath, "w") as f:
            json.dump(self.geojson, f, indent=4)
