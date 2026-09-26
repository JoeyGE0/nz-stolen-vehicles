"""Constants for NZ Stolen Vehicles."""

DOMAIN = "nz_stolen_vehicles"
ATTRIBUTION = "Data from New Zealand Police stolen vehicles register"

CONF_DISTRICT = "district"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_DISTRICT = "all"
DEFAULT_SCAN_INTERVAL = 6

DOWNLOAD_URL = (
    "https://www.police.govt.nz/stolenwanted/vehicles/csv/download"
)
POLICE_PAGE_URL = "https://www.police.govt.nz/can-you-help-us/stolen-vehicles"
USER_AGENT = (
    "HomeAssistant-NZStolenVehicles/1.0 "
    "(+https://github.com/JoeyGE0/nz-stolen-vehicles)"
)

EVENT_MATCH = "nz_stolen_vehicles_match"
SERVICE_CHECK_PLATE = "check_plate"

DISTRICTS: dict[str, str] = {
    "all": "All of New Zealand",
    "117": "Auckland City",
    "118": "Bay of Plenty",
    "119": "Canterbury",
    "120": "Central",
    "121": "Counties/Manukau",
    "122": "Eastern",
    "123": "Northland",
    "126": "Southern",
    "127": "Tasman",
    "128": "Waikato",
    "129": "Waitematā",
    "130": "Wellington",
}


def district_label(district: str) -> str:
    """Return the display name for a district id."""
    return DISTRICTS.get(district, district)


def download_url(district: str) -> str:
    """Build the Police CSV download URL for a district."""
    if district == "all":
        return f"{DOWNLOAD_URL}?all=true&gzip=false"
    return f"{DOWNLOAD_URL}?tid={district}&all=false&gzip=false"


def normalize_plate(plate: str) -> str:
    """Normalise a plate for lookup: uppercase, alphanumeric only."""
    return "".join(char for char in plate.upper() if char.isalnum())
