from functools import partial
from typing import List, Tuple, Union
from datetime import datetime, timedelta

# --- Configuration Keys (Constants) ---
# These remain unchanged as they are clear and effective.
CONFIG_IF_DIRECTORY_EMPTY = "if_directory_empty"
CONFIG_DOWNLOADS_LIMIT = "downloads_limit"
CONFIG_FILE_NAME_TEMPLATE = "file_name_template"
CONFIG_PODCAST_EXTENSIONS = "podcast_extensions"
CONFIG_HTTP_HEADER = "http_headers"
CONFIG_FILL_UP_GAPS = "fill_up_gaps"
CONFIG_DOWNLOAD_DELAY = "download_delay"
CONFIG_LAST_RUN_MARK_PATH = "last_run_mark_file_path"

CONFIG_PODCASTS = "podcasts"
CONFIG_PODCASTS_NAME = "name"
CONFIG_PODCASTS_PATH = "path"
CONFIG_PODCASTS_RSS_LINK = "rss_link"
CONFIG_PODCASTS_REQUIRE_DATE = "require_date"
CONFIG_PODCASTS_DISABLE = "disable"

WEEK_DAYS = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)

# --- Custom Exception for Clearer Error Handling ---
class ConfigurationError(ValueError):
    """Custom exception for errors found in the configuration."""
    pass


# --- Functions ---

def configuration_verification(config: dict) -> None:
    """
    Verifies the podcast configuration, raising an error if invalid.
    
    Args:
        config: The configuration dictionary.

    Raises:
        ConfigurationError: If a required key is missing for a podcast.
    """
    if CONFIG_PODCASTS not in config or not isinstance(config[CONFIG_PODCASTS], list):
        raise ConfigurationError(f"The '{CONFIG_PODCASTS}' key is missing or is not a list.")

    for i, podcast in enumerate(config[CONFIG_PODCASTS]):
        podcast_name = podcast.get(CONFIG_PODCASTS_NAME, f"unnamed podcast at index {i}")
        
        if not CONFIG_PODCASTS_PATH in podcast:
            raise ConfigurationError(f"There is no '{CONFIG_PODCASTS_PATH}' key for podcast '{podcast_name}'")
        
        if not CONFIG_PODCASTS_RSS_LINK in podcast:
            raise ConfigurationError(f"There is no '{CONFIG_PODCASTS_RSS_LINK}' key for podcast '{podcast_name}'")


def get_n_age_date(day_number: int, from_date: datetime) -> datetime:
    """
    Calculates a date that is `day_number` days before `from_date`.

    Args:
        day_number: The number of days to go back.
        from_date: The starting date.

    Returns:
        The resulting past date as a datetime object.
    """
    return from_date - timedelta(days=day_number)


def get_week_day(weekday_label: str, from_date: datetime) -> datetime:
    """
    Finds the date of the last occurrence of a given weekday before or on `from_date`.

    Args:
        weekday_label: The name of the weekday (e.g., "Monday").
        from_date: The starting date.

    Returns:
        The date of the last specified weekday.
    """
    target_weekday_index = WEEK_DAYS.index(weekday_label)
    days_ago = (from_date.weekday() - target_weekday_index + 7) % 7
    # If today is the target day, get the one from last week.
    if days_ago == 0:
        days_ago = 7
    return from_date - timedelta(days=days_ago)


def get_nth_day(day_of_month: int, from_date: datetime) -> datetime:
    """
    Finds the date of the last time it was the Nth day of a month.

    Args:
        day_of_month: The day of the month (1-31).
        from_date: The starting date.

    Returns:
        The date of the last Nth day.
    """
    if from_date.day >= day_of_month:
        # The last Nth day was in the current month.
        return from_date.replace(day=day_of_month)
    else:
        # The last Nth day was in the previous month.
        # Go to the first day of the current month, then go back one day to get to the previous month.
        last_day_of_previous_month = from_date.replace(day=1) - timedelta(days=1)
        return last_day_of_previous_month.replace(day=day_of_month)


def parse_day_label(raw_label: str) -> Union[str, int]:
    """
    Parses a string label into either an integer day or a weekday string.

    Args:
        raw_label: The input string (e.g., "1st", "15th", "Monday", "mon").

    Returns:
        An integer for a day of the month, or a capitalized weekday string.
    """
    # Handle numeric days with suffixes (e.g., "1st", "2nd", "3rd", "4th")
    label = raw_label.lower()
    if label.endswith(("st", "nd", "rd", "th")):
        return int(label[:-2])

    if label.isnumeric():
        return int(label)

    # Handle weekday names (e.g., "Monday", "mon")
    capitalize_raw_label = raw_label.capitalize()
    short_weekdays = {
        "Mon": "Monday", "Tue": "Tuesday", "Wed": "Wednesday",
        "Thu": "Thursday", "Fri": "Friday", "Sat": "Saturday", "Sun": "Sunday"
    }

    if capitalize_raw_label in WEEK_DAYS:
        return capitalize_raw_label
    
    if capitalize_raw_label in short_weekdays:
        return short_weekdays[capitalize_raw_label]

    raise ValueError(f"Cannot parse day label '{raw_label}'")


def get_label_to_date(day_label: Union[str, int]) -> partial:
    """
    Returns a function to calculate a date based on a parsed label.
    This now works with datetime objects.

    Args:
        day_label: A weekday string or a day-of-the-month integer.

    Returns:
        A partial function that takes a `from_date` datetime object and returns a past date.
    """
    if isinstance(day_label, str) and day_label in WEEK_DAYS:
        return partial(get_week_day, day_label)
    
    if isinstance(day_label, int):
        return partial(get_nth_day, day_label)

    # This case should ideally not be reached if parse_day_label works correctly.
    raise TypeError(f"Unsupported label type for date calculation: {day_label}")
