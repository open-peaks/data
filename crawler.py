#!/usr/bin/env python3
import traceback
from typing import List, Set

from bs4 import BeautifulSoup

from peak import Peak
from utils import get_cache


def _clean_url(href: str) -> str:
    if href is None:
        href = "https://en.wikipedia.org"
    if href.startswith("//"):
        href = "https:" + href
    if href.startswith("/w/"):
        href = "https://en.wikipedia.org" + href
    if href.startswith("/wiki/"):
        href = "https://en.wikipedia.org" + href
    if "&" in href:
        href = href.split("&")[0]
    href = href.replace("/w/index.php?title=", "/wiki/")
    return href


def get_list_urls(url: str, good_keys: List[str], bad_keys:List[str], visited_urls=None) -> str:

    def _is_bad_url(href: str, good_keys: List[str], bad_keys: List[str]) -> bool:
        # ignore bad HREFs
        found_bad_key = False
        for bad_key in bad_keys:
            if bad_key in href:
                found_bad_key = True
                break
        if found_bad_key:
            return True
        found_good_key = False
        for good_key in good_keys:
            if good_key in href:
                found_good_key = True
                break
        if not found_good_key:
            return True
        if not href.startswith("https://en.wikipedia.org"):
            return True

        return False

    if visited_urls is None:
        visited_urls = set()
    url = _clean_url(url)
    if url in visited_urls:
        return
    visited_urls.add(url)
    yield "https://en.wikipedia.org/wiki/List_of_mountains_of_British_Columbia"

    content = get_cache(url)
    if content is None:
        return
    soup = BeautifulSoup(content, 'html.parser')
    links = soup.find_all('a')
    for link in links:
        href = _clean_url(link.get('href'))
        if _is_bad_url(href, good_keys, bad_keys):
            continue

        category = href.split("Category:")[1]
        if category.startswith("Lists") or category.startswith("Mountains"):
            yield url
            for list_url in get_list_urls(href, good_keys, bad_keys, visited_urls):
                yield list_url
        else:
            yield href


def _strip_peak_urls_from_list_page(url: str) -> List[str]:

    def _is_peak_url(href: str) -> bool:
        if not href.startswith("https://en.wikipedia.org/wiki/"):
            return False
        path = href.split("/wiki/")[1]
        if ":" in path:
            return False
        bad_path_starts = [
            "List_of",
            "Lists_of",
            "Mountains_",
            "Database_of_",
            "Category:",
            "File:",
            "Template:",
            "Help:",
            "Portal:",
            "Special:",
            "Wikipedia:",
        ]
        for bad_path_start in bad_path_starts:
            if path.startswith(bad_path_start):
                return False

        bad_words = ["ranges", "hills", "mountains", "peaks", "summits"]
        for bad_word in bad_words:
            if bad_word in path.lower():
                return False

        def _infobox(href: str) -> {}:
            infobox_data = {}
            content = get_cache(href)
            if content is None:
                return {}
            soup = BeautifulSoup(content, 'html.parser')
            # Get rows of infobox
            table = soup.find('table', {'class': 'infobox'})
            if table is None:
                return {}
            rows = table.find_all('tr')
            for row in rows:
                th = row.find('th')
                if th is None:
                    continue
                td = row.find('td')
                if td is None:
                    continue
                infobox_data[th.text] = td.text
            return infobox_data

        infobox_data = _infobox(href)
        required_keys = [
            "Elevation",
            "Coordinates",
            "Parent range",
        ]
        for required_key in required_keys:
            if required_key not in infobox_data:
                return False
        return True

    content = get_cache(url)
    soup = BeautifulSoup(content, 'html.parser')
    links = soup.find_all('a')
    for link in links:
        href = _clean_url(link.get('href'))
        if href.startswith("https://en.wikipedia.org/wiki/"):
            if _is_peak_url(href):
                yield href


def get_peak_urls(base_list_url: str):
    visited_peak_urls: Set[str] = set()
    for list_url in get_list_urls(
        base_list_url,
        [
            "Category:Mountains_of_",
            "Category:Lists_of_mountains",
            "Category:Lists_of_peaks",
         ],
        [
            "Category_talk",
            "Special",
            "Category:Nature-related_lists",
            "related",
            "Landforms",
            "_ranges_",
            "Main_Page",
        ]
    ):
        urls = _strip_peak_urls_from_list_page(list_url)
        for peak_url in urls:
            if peak_url in visited_peak_urls:
                continue
            visited_peak_urls.add(peak_url)
            yield peak_url


def peak_names():
    base_url = "https://en.wikipedia.org/wiki/Category:Lists_of_mountains"
    for url in get_peak_urls(base_url):
        name = url.split("/wiki/")[1].replace("_", " ")
        yield name, url


if __name__ == "__main__":
    i = 1
    for name, url in peak_names():
        try:
            peak = Peak(name, url)
            peak.flesh_out()
            print(f"{i}\t{peak}")
            peak.save()
        except Exception as e:
            traceback.print_exc()
            print("FAILED ON", name, url)

        i += 1
