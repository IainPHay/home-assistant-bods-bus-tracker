"""Constants for BODS Bus Tracker."""

from __future__ import annotations

DOMAIN = "bods_bus_tracker"
VERSION = "0.4.2"
PLATFORMS = ["sensor", "binary_sensor"]
SUBENTRY_TYPE_STOP = "stop"

CONF_API_KEY = "api_key"
CONF_REGION = "region"
CONF_STOP_ATCO = "stop_atco"
CONF_STOP_NAME = "stop_name"
CONF_STOP_SEARCH = "stop_search"
CONF_STOP_SELECTION = "stop_selection"
CONF_SERVICES = "services"
CONF_POLL_INTERVAL = "poll_interval"
CONF_LEGACY_ENTITY_IDS = "legacy_entity_ids"
CONF_WALKING_TIME = "walking_time"

AUTO_REGION = "auto"
DEFAULT_POLL_INTERVAL = 30
MIN_POLL_INTERVAL = 15
MAX_POLL_INTERVAL = 300
DEFAULT_WALKING_TIME = 0
MIN_WALKING_TIME = 0
MAX_WALKING_TIME = 120
DEFAULT_GTFS_REFRESH_HOURS = 24
MAX_LIVE_AGE_SECONDS = 180
STOP_SEARCH_LIMIT = 25

BODS_VEHICLE_URL = "https://data.bus-data.dft.gov.uk/api/v1/datafeed/"
GTFS_URL_TEMPLATE = (
    "https://data.bus-data.dft.gov.uk/timetable/download/gtfs-file/{region}/"
)

REGIONS: dict[str, str] = {
    "east_anglia": "East Anglia",
    "east_midlands": "East Midlands",
    "london": "London",
    "north_east": "North East",
    "north_west": "North West",
    "south_east": "South East",
    "south_west": "South West",
    "west_midlands": "West Midlands",
    "yorkshire": "Yorkshire",
}

REGION_CENTRES: dict[str, tuple[float, float]] = {
    "north_east": (54.95, -1.60),
    "north_west": (53.65, -2.70),
    "yorkshire": (53.80, -1.50),
    "east_midlands": (52.95, -1.10),
    "west_midlands": (52.50, -2.00),
    "east_anglia": (52.30, 0.35),
    "london": (51.51, -0.12),
    "south_east": (51.20, 0.15),
    "south_west": (50.90, -3.00),
}

CACHE_DIR = ".bods_bus_tracker_cache"
LOCAL_TIME_ZONE = "Europe/London"
SERVICE_SEPARATOR = "|"
