import requests
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import sleep
import threading
import math
import os

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# --- Global storage ---
_wca_persons_data = {}
_wca_competitions_data = {}
_wca_comparison_data = {} # <-- ADD THIS LINE to store the comparison data
_data_loaded_event = threading.Event()
_is_loading = False

# --- Config ---
BASE_URL_PERSONS = "https://raw.githubusercontent.com/robiningelbrecht/wca-rest-api/master/api/persons-page-{}.json"
BASE_URL_COMPETITIONS = "https://raw.githubusercontent.com/robiningelbrecht/wca-rest-api/master/api/competitions-page-{}.json"
BASE_URL_COUNTRIES = "https://raw.githubusercontent.com/robiningelbrecht/wca-rest-api/master/api/countries.json"
TOTAL_PERSON_PAGES = 268
MAX_RETRIES = 5
THREADS = 16

# --- Continent Map ---
continent_map = {
    # Europe
    "AD": "europe", "AL": "europe", "AM": "europe", "AT": "europe", "AZ": "europe", "BA": "europe", "BE": "europe",
    "BG": "europe", "BY": "europe", "CH": "europe", "CZ": "europe", "DE": "europe", "DK": "europe", "EE": "europe",
    "ES": "europe", "FI": "europe", "FR": "europe", "GB": "europe", "GE": "europe", "GR": "europe", "HU": "europe",
    "IE": "europe", "IS": "europe", "IT": "europe", "KZ": "europe", "LI": "europe", "LT": "europe", "LU": "europe",
    "LV": "europe", "MD": "europe", "MC": "europe", "ME": "europe", "MK": "europe", "NL": "europe", "NO": "europe",
    "PL": "europe", "PT": "europe", "RO": "europe", "RS": "europe", "RU": "europe", "SE": "europe", "SI": "europe",
    "SK": "europe", "SM": "europe", "UA": "europe", "VA": "europe", "XK": "europe",

    # Asia
    "AE": "asia", "AF": "asia", "BH": "asia", "BD": "asia", "BT": "asia", "BN": "asia", "KH": "asia", "CN": "asia",
    "CY": "asia", "TL": "asia", "IN": "asia", "ID": "asia", "IR": "asia", "IQ": "asia", "IL": "asia", "JP": "asia",
    "JO": "asia", "KG": "asia", "KW": "asia", "LA": "asia", "LB": "asia", "MY": "asia", "MV": "asia", "MN": "asia",
    "MM": "asia", "NP": "asia", "KP": "asia", "KR": "asia", "OM": "asia", "PK": "asia", "PS": "asia", "QA": "asia",
    "SA": "asia", "SG": "asia", "LK": "asia", "SY": "asia", "TJ": "asia", "TH": "asia", "TM": "asia", "UZ": "asia",
    "VN": "asia", "YE": "asia", "XA": "asia",

    # Africa
    "DZ": "africa", "AO": "africa", "BJ": "africa", "BW": "africa", "BF": "africa", "BI": "africa", "CM": "africa",
    "CV": "africa", "CF": "africa", "TD": "africa", "KM": "africa", "CG": "africa", "CD": "africa", "CI": "africa",
    "DJ": "africa", "EG": "africa", "GQ": "africa", "ER": "africa", "SZ": "africa", "ET": "africa", "GA": "africa",
    "GM": "africa", "GH": "africa", "GN": "africa", "GW": "africa", "KE": "africa", "LS": "africa", "LR": "africa",
    "LY": "africa", "MG": "africa", "MW": "africa", "ML": "africa", "MR": "africa", "MU": "africa", "MA": "africa",
    "MZ": "africa", "NA": "africa", "NE": "africa", "NG": "africa", "RW": "africa", "ST": "africa", "SN": "africa",
    "SC": "africa", "SL": "africa", "SO": "africa", "ZA": "africa", "SS": "africa", "SD": "africa", "TZ": "africa",
    "TG": "africa", "TN": "africa", "UG": "africa", "ZM": "africa", "ZW": "africa", "XF": "africa",

    # North America
    "AG": "north-america", "BS": "north-america", "BB": "north-america", "BZ": "north-america", "CA": "north-america",
    "CR": "north-america", "CU": "north-america", "DM": "north-america", "DO": "north-america", "SV": "north-america",
    "GD": "north-america", "GT": "north-america", "HT": "north-america", "HN": "north-america", "JM": "north-america",
    "MX": "north-america", "NI": "north-america", "PA": "north-america", "KN": "north-america", "LC": "north-america",
    "VC": "north-america", "TT": "north-america", "US": "north-america", "XN": "north-america",

    # South America
    "AR": "south-america", "BO": "south-america", "BR": "south-america", "CL": "south-america", "CO": "south-america",
    "EC": "south-america", "GY": "south-america", "PY": "south-america", "PE": "south-america", "SR": "south-america",
    "UY": "south-america", "VE": "south-america", "XS": "south-america",

    # Oceania
    "AU": "oceania", "NZ": "oceania", "FJ": "oceania", "FM": "oceania", "KI": "oceania", "MH": "oceania", "NR": "oceania",
    "PW": "oceania", "PG": "oceania", "SB": "oceania", "TO": "oceania", "TV": "oceania", "VU": "oceania", "WS": "oceania",
    "XO": "oceania",

    # Misc
    "XM": "americas", "XE": "europe", "XA": "asia", "XF": "africa", "XW": "world"
}

# --- Utility Functions ---
def fetch_page(url: str, page_number: int):
    """Fetch a single page of data with retries."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            full_url = url.format(page_number)
            r = requests.get(full_url, timeout=30)
            r.raise_for_status()
            logger.info(f"Page {page_number} fetched successfully from {full_url}.")
            return r.json()
        except requests.exceptions.RequestException as e:
            wait_time = attempt * 5
            logger.warning(f"Error fetching page {page_number} (attempt {attempt}): {e}. Retrying in {wait_time}s...")
            sleep(wait_time)
    logger.error(f"Failed to fetch page {page_number} after {MAX_RETRIES} attempts.")
    return None

def find_fastest_comparisons():
    """Finds the fastest competitors for each event combination."""
    global _wca_persons_data, _wca_comparison_data
    
    event_ids = ["333", "222", "444", "555", "666", "777", "333bf", "333oh",
                 "333fm", "clock", "minx", "pyram", "sq1", "skewb", "444bf",
                 "555bf", "333mbf"]
    
    logger.info("Starting comparison data pre-computation...")
    
    # Pre-filter persons to those with at least two single results
    eligible_persons = {
        p_id: p_data
        for p_id, p_data in _wca_persons_data.items()
        if p_data.get("rank", {}).get("singles") and len(p_data["rank"]["singles"]) >= 2
    }
    
    # Generate all unique event pairs
    event_pairs = []
    for i in range(len(event_ids)):
        for j in range(i + 1, len(event_ids)):
            event_pairs.append((event_ids[i], event_ids[j]))

    # Dictionary to store the fastest competitors for each pair
    comparison_data_temp = {}
    
    # Iterate through all event pairs
    for event1, event2 in event_pairs:
        temp_list = []
        for person_id, person in eligible_persons.items():
            ranks = person["rank"]["singles"]
            result1 = None
            result2 = None
            
            # Find results for both events
            for rank_info in ranks:
                if rank_info["eventId"] == event1:
                    result1 = rank_info["best"]
                if rank_info["eventId"] == event2:
                    result2 = rank_info["best"]
            
            if result1 is not None and result2 is not None:
                # Only compare if both results are valid (not DNF)
                if result1 > 0 and result2 > 0:
                    time_diff = (result1 - result2) / 100.0
                    temp_list.append({
                        "name": person["name"],
                        "wca_id": person["id"],
                        "country": person["country"],
                        "best1": result1,
                        "best2": result2,
                        "diff": time_diff
                    })

        # Sort the list by the time difference (fastest time difference first)
        sorted_list = sorted(temp_list, key=lambda x: x["diff"])
        
        # Store the top results for this event pair (e.g., top 100)
        comparison_data_temp[tuple(sorted((event1, event2)))] = sorted_list[:100]

    _wca_comparison_data = comparison_data_temp
    logger.info("Comparison data pre-computation complete.")


def preload_wca_data_thread():
    """Preload all WCA persons and competitions data in parallel."""
    global _wca_persons_data, _wca_competitions_data, _wca_comparison_data, _data_loaded_event, _is_loading

    if _is_loading:
        logger.info("Data preload already in progress.")
        return

    _is_loading = True
    _data_loaded_event.clear()
    logger.info("Starting WCA data preload...")

    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        # Competitions
        first_comp_page = fetch_page(BASE_URL_COMPETITIONS, 1)
        if first_comp_page:
            total_comp = first_comp_page.get("total", 0)
            page_size = first_comp_page.get("pagination", {}).get("size", 1000)
            total_pages = math.ceil(total_comp / page_size)

            comp_data = {c["id"]: c["date"]["till"] for c in first_comp_page.get("items", [])}

            futures = {executor.submit(fetch_page, BASE_URL_COMPETITIONS, p): p for p in range(2, total_pages + 1)}
            for future in as_completed(futures):
                data = future.result()
                if data and data.get("items"):
                    for c in data["items"]:
                        comp_data[c["id"]] = c["date"]["till"]
            _wca_competitions_data.update(comp_data)

        # Persons
        futures = {executor.submit(fetch_page, BASE_URL_PERSONS, p): p for p in range(1, TOTAL_PERSON_PAGES + 1)}
        persons_data = {}
        for future in as_completed(futures):
            data = future.result()
            if data and data.get("items"):
                for person in data["items"]:
                    pid = person.get("id")
                    if pid:
                        persons_data[pid] = person
        _wca_persons_data.update(persons_data)

    # --- ADD THIS LOGIC TO PRE-COMPUTE COMPARISON DATA ---
    find_fastest_comparisons()
    
    _is_loading = False
    _data_loaded_event.set()
    logger.info(f"WCA preload complete: {len(_wca_persons_data)} persons, {len(_wca_competitions_data)} competitions, {len(_wca_comparison_data)} comparisons.")


def is_wca_data_loaded():
    return _data_loaded_event.is_set()


def get_all_wca_persons_data():
    if not _data_loaded_event.is_set():
        logger.warning("Waiting for WCA data to load...")
        _data_loaded_event.wait(timeout=180)
        if not _data_loaded_event.is_set():
            logger.error("Timeout: WCA data not loaded.")
            return {}
    return _wca_persons_data


def get_all_wca_competitions_data():
    return _wca_competitions_data

# --- ADD THIS NEW GETTER FUNCTION ---
def get_all_wca_comparison_data():
    if not _data_loaded_event.is_set():
        logger.warning("Waiting for comparison data to load...")
        _data_loaded_event.wait(timeout=180)
        if not _data_loaded_event.is_set():
            logger.error("Timeout: Comparison data not loaded.")
            return {}
    return _wca_comparison_data


# --- Start preload on import ---
threading.Thread(target=preload_wca_data_thread, daemon=True).start()