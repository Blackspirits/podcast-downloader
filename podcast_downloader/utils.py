import sys
import time
import logging
import argparse
import re # Added re import for ConsoleOutputFormatter
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from functools import partial, reduce # Added reduce import for compose
from typing import Callable, Dict, Iterable, Any, List, Tuple # Added Any, List, Tuple for type hinting

import requests

from .configuration import (
    ConfigurationError,
    configuration_verification,
    get_label_to_date,
    get_n_age_date,
    parse_day_label,
)
from .downloaded import (
    get_downloaded_files,
    get_extensions_checker,
    get_last_downloaded_file_before_gap,
)
from .parameters import merge_parameters_collection, load_configuration_file, parse_argv
from .rss import (
    RSSEntity,
    build_only_allowed_filter_for_link_data,
    build_only_new_entities,
    file_template_to_file_name,
    flatten_rss_links_data,
    get_feed_title_from_feed,
    get_raw_rss_entries_from_feed,
    limit_file_name,
    load_feed,
    only_entities_from_date,
    only_last_n_entities,
)

# --- Define ConsoleOutputFormatter and compose here to ensure they are available ---
class ConsoleOutputFormatter(logging.Formatter):
    """
    An advanced logging formatter that uses special cases and regex patterns
    to apply Catppuccin Mocha colors to log messages.
    """

    RESET = "\033[0m"

    # --- Catppuccin Mocha Palette ---
    RED = "\033[38;2;243;139;168m"
    GREEN = "\033[38;2;166;227;161m"
    YELLOW = "\033[38;2;249;226;175m"
    BLUE = "\033[38;2;137;180;250m"
    CYAN = "\033[38;2;148;226;213m"
    WHITE = "\033[38;2;186;194;222m"
    BRIGHT_BLACK = "\033[38;2;88;91;112m"
    ROSEWATER = "\033[38;2;245;224;220m"
    FLAMINGO = "\033[38;2;242;205;205m"
    MAUVE = "\033[38;2;203;166;247m"
    LAVENDER = "\033[38;2;180;190;254m"
    MAROON = "\033[38;2;235;160;172m"
    SKY = "\033[38;2;137;220;235m"
    OVERLAY2 = "\033[38;2;147;153;178m"
    PINK = "\033[38;2;245;194;231m"

    LEVEL_COLORS = {
        logging.DEBUG: BRIGHT_BLACK,
        logging.INFO: BLUE,
        logging.WARNING: YELLOW,
        logging.ERROR: RED,
        logging.CRITICAL: RED, # Good to include CRITICAL if not already
    }

    KEYWORD_RULES: List[Tuple[str, str]] = [
        (r'\b(Checking)\b', BLUE),
        (r'\b(Last downloaded file:)\b', BLUE),
        (r'(".*?")', ROSEWATER),
        (r'\b(Finished\.)', GREEN),
        (r'\b(Nothing new to download\.)', MAUVE),
    ]

    def __init__(self) -> None:
        # CORRECTED: Only pass datefmt, as you are fully overriding the format method.
        # This resolves the KeyError/ValueError.
        super().__init__(datefmt="%Y-%m-%d %H:%M:%S") 

        # OPTIONAL: Pre-compile regex patterns for efficiency if rules are extensive/used frequently
        self._compiled_keyword_rules = [(re.compile(pattern), color) for pattern, color in self.KEYWORD_RULES]


    def format(self, record: logging.LogRecord) -> str:
        timestamp = self.formatTime(record, self.datefmt)
        # _format_message correctly calls self.formatMessage(record) internally
        message = self._format_message(record)
        prefix = f"{self.OVERLAY2}[{self.RESET}{self.FLAMINGO}{timestamp}{self.RESET}{self.OVERLAY2}]{self.RESET} "
        return prefix + message

    def _format_message(self, record: logging.LogRecord) -> str:
        # `message` now contains the fully interpolated string (e.g., "%s" replaced by actual args)
        message = self.formatMessage(record)

        # Special case formatting based on full `record.msg` content
        # Adjusted regex to match the log output you showed previously:
        if record.msg.startswith("Loaded configuration from file:"):
            return re.sub(
                r'(Loaded configuration from file: )(".*?")',
                lambda m: f"{self.CYAN}{m.group(1)}{self.RESET}{self.WHITE}{m.group(2)}{self.RESET}",
                message
            )
        elif record.msg.startswith('Checking feed "'):
            return re.sub(
                r'(Checking feed )(".*?")',
                lambda m: f"{self.BLUE}{m.group(1)}{self.RESET}{self.ROSEWATER}{m.group(2)}{self.RESET}",
                message
            )
        elif record.msg.startswith('Last downloaded file: "'):
            return re.sub(
                r'(Last downloaded file: )(".*?")',
                lambda m: f"{self.BLUE}{m.group(1)}{self.RESET}{self.ROSEWATER}{m.group(2)}{self.RESET}",
                message
            )
        elif record.msg.startswith('Downloading new episode from "') and record.args:
            # Example message: 'Downloading new episode from "Podcast Name"'
            return re.sub(r'(Downloading new episode from )(".*?")',
                          lambda m: f"{self.CYAN}{m.group(1)}{self.ROSEWATER}{m.group(2)}{self.RESET}",
                          message)

        elif record.msg.strip().startswith("-> Source URL:") and record.args:
            # message will be "-> Source URL: "http://example.com/url""
            # Use split to get the URL part and apply color
            return f"    {self.LAVENDER}-> Source URL:{self.RESET} {self.SKY}{message.split(': ', 1)[1]}{self.RESET}"

        elif record.msg.strip().startswith("-> Saving as:") and record.args:
            # message will be "-> Saving as: "/path/to/file""
            # Use split to get the path part and apply color
            return f"    {self.LAVENDER}-> Saving as:{self.RESET} {self.MAROON}{message.split(': ', 1)[1]}{self.RESET}"

        # Apply default level coloring first
        color = self.LEVEL_COLORS.get(record.levelno, self.BLUE)
        colored = f"{color}{message}{self.RESET}"

        # Apply keyword rules. Using pre-compiled patterns for efficiency.
        for compiled_pattern, keyword_color in self._compiled_keyword_rules:
            # The lambda function uses the `color` (level color) to reset to after the keyword
            # This ensures that subsequent text after the keyword retains the original log level color.
            colored = compiled_pattern.sub(lambda m: f"{keyword_color}{m.group(1)}{color}", colored)

        if record.exc_info:
            # Color the exception text specifically in RED for errors
            colored += "\n" + f"{self.RED}{self.formatException(record.exc_info)}{self.RESET}"

        return colored

def compose(*functions: Callable[[Any], Any]) -> Callable[[Any], Any]:
    """
    Composes single-argument functions from right to left:
    compose(f, g, h)(x) == f(g(h(x)))
    """
    if not functions:
        raise ValueError("At least one function must be provided.")
    return reduce(lambda f, g: lambda x: f(g(x)), functions)

# --- Logger Setup ---
logger = logging.getLogger("podcast_downloader")
logger.setLevel(logging.INFO)
# Ensure handlers are only added once to prevent duplicate log messages
if not logger.handlers:
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(ConsoleOutputFormatter())
    logger.addHandler(handler)

@dataclass
class ProcessingStats:
    downloads: int = 0
    skipped: int = 0
    errors: int = 0

def download_rss_entity_to_path(
    headers: Dict[str, str],
    to_file_name_function: Callable[[RSSEntity], str],
    path: Path,
    rss_entity: RSSEntity,
):
    path.mkdir(parents=True, exist_ok=True)
    path_to_file = path / to_file_name_function(rss_entity)

    try:
        with requests.get(rss_entity.link, headers=headers, stream=True, timeout=30) as response:
            response.raise_for_status()
            with open(path_to_file, "wb") as file:
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)
    except requests.exceptions.RequestException as e:
        logger.error('Network error while trying to download "%s": %s', rss_entity.link, e)
    except IOError as e:
        logger.error('Failed to save file "%s" to disk: %s', path_to_file, e)
    except Exception as e:
        logger.exception('Unexpected error downloading "%s" to "%s": %s', rss_entity.link, path_to_file, e)

def build_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--downloads_limit", type=int, help="Maximum number of files to download.")
    parser.add_argument("--if_directory_empty", type=str, help="Behaviour if directory is empty.")
    parser.add_argument("--config", type=str, help="Path to configuration file.")
    parser.add_argument("--download_delay", type=int, help="Delay in seconds between downloads.")
    parser.add_argument("--dry_run", action="store_true", help="If set, do not perform actual downloads.")
    return parser

def setup_configuration(args) -> Dict[str, Any]: # Type hinted the return
    DEFAULT_CONFIGURATION = {
        "downloads_limit": sys.maxsize,
        "if_directory_empty": "download_last",
        "podcast_extensions": {".mp3": "audio/mpeg"},
        "file_name_template": "%title%.%file_extension%",
        "http_headers": {"User-Agent": f"podcast-downloader/1.0 (Python/{sys.version_info.major}.{sys.version_info.minor})"},
        "fill_up_gaps": False,
        "download_delay": 0,
        "last_run_mark_file_path": None,
        "podcasts": [],
        "dry_run": False,
    }
    config_file_name = args.config or "~/.podcast_downloader_config.json"
    config_path = Path(config_file_name).expanduser()
    try:
        config_file_data = load_configuration_file(config_path)
        logger.info('Loaded configuration from file: "%s"', config_path)
    except (FileNotFoundError, ValueError) as e:
        logger.warning("Could not load configuration file: %s. Using defaults and CLI args.", e)
        config_file_data = {}

    merged = merge_parameters_collection(DEFAULT_CONFIGURATION, config_file_data, vars(args))
    configuration_verification(merged)
    return merged

def load_the_last_run_date_store_now(marker_file_path_str: str, now: datetime):
    if not marker_file_path_str:
        return None
    marker_file = Path(marker_file_path_str).expanduser()
    if not marker_file.exists():
        logger.warning("Marker file does not exist; creating new one with current time.")
        marker_file.parent.mkdir(parents=True, exist_ok=True)
        # Use 'touch()' to create/update timestamp, which is often sufficient for marker files
        marker_file.touch()
        # Optionally, write some content if the file must not be empty
        # with open(marker_file, "a") as f:
        #     f.write("Marker file for podcast_downloader.\n")
        return now
    
    # Get last access time. St_atime is more appropriate for "last run detected" than st_mtime.
    access_time_stamp = marker_file.stat().st_atime 
    access_time = datetime.fromtimestamp(access_time_stamp)
    logger.info("Last run time detected: %s", access_time.strftime("%Y-%m-%d %H:%M:%S"))
    
    # Update the access and modification times to current time
    marker_file.touch() # This updates modification time to now. Also updates access time on some systems.
    # If explicit access/modification time setting is needed for cross-platform consistency:
    # now_timestamp = time.mktime(now.timetuple())
    # marker_file.utime((now_timestamp, now_timestamp)) 
    
    return access_time


def configuration_to_function_on_empty_directory(configuration_value: str, last_run_date: datetime):
    if configuration_value == "download_last":
        return partial(only_last_n_entities, 1)
    if configuration_value == "download_all_from_feed":
        return lambda source: source
    if configuration_value == "download_since_last_run":
        if last_run_date:
            return partial(filter, only_entities_from_date(last_run_date))
        logger.error('Option "download_since_last_run" requires last run marker file to be set.')
        raise Exception("Missing last run marker file")
    # Matches like download_from_10_days, download_last_5_episodes, download_from_2023-06-01, etc
    local_time = datetime.now()
    if match := re.match(r"^download_from_(\d+)_days$", configuration_value):
        from_date = get_n_age_date(int(match[1]), local_time)
        return partial(filter, only_entities_from_date(from_date))
    if match := re.match(r"^download_last_(\d+)_episodes$", configuration_value):
        download_limit = int(match[1])
        return partial(only_last_n_entities, download_limit)
    if match := re.match(r"^download_from_(.*)$", configuration_value):
        day_label = parse_day_label(match[1])
        date_func = get_label_to_date(day_label)
        from_date = date_func(local_time)
        return partial(filter, only_entities_from_date(from_date))
    raise Exception(f"Unrecognized 'if_directory_empty' value: '{configuration_value}'")

def get_system_file_name_limit(sub_configuration: dict) -> int:
    path_str = str(sub_configuration.get("path", ""))
    # Windows max path ~260, adjust for length of folder path
    return 255 if sys.platform == "win32" else 260 - len(path_str) - 1

def configuration_to_function_rss_to_name(configuration_value: str, sub_configuration: dict) -> Callable[[RSSEntity], str]:
    return partial(file_template_to_file_name, configuration_value)

def process_podcast_feed(
    podcast_config: dict,
    global_config: dict,
    last_run_date: datetime,
    dry_run: bool,
) -> ProcessingStats:
    stats = ProcessingStats()
    try:
        rss_source_name = podcast_config.get("name") or None
        rss_source_path = Path(podcast_config["path"]).expanduser()
        rss_source_link = podcast_config["rss_link"]
        if podcast_config.get("disable", False):
            logger.info('Skipping "%s" (disabled)', rss_source_name or rss_source_link)
            stats.skipped += 1
            return stats

        feed = load_feed(rss_source_link)
        if feed.bozo and not feed.entries:
            logger.error("Error checking feed '%s': %s", rss_source_link, feed.bozo_exception)
            stats.errors += 1
            return stats

        if not rss_source_name:
            rss_source_name = get_feed_title_from_feed(feed)

        logger.info('Checking feed "%s"', rss_source_name)

        to_name_function = configuration_to_function_rss_to_name(podcast_config["file_name_template"], podcast_config)
        file_length_limit = get_system_file_name_limit(podcast_config)
        to_real_file_name = compose(partial(limit_file_name, file_length_limit), to_name_function)

        extensions_checker = get_extensions_checker(podcast_config["podcast_extensions"].keys())
        downloaded_files = list(get_downloaded_files(extensions_checker, rss_source_path))
        allow_link_types = list(set(podcast_config["podcast_extensions"].values()))

        all_feed_entries = list(filter(build_only_allowed_filter_for_link_data(allow_link_types), flatten_rss_links_data(get_raw_rss_entries_from_feed(feed))))

        all_feed_files = [to_real_file_name(entry) for entry in all_feed_entries][::-1]
        downloaded_files_set = set(downloaded_files)

        if not downloaded_files_set:
            download_limiter = configuration_to_function_on_empty_directory(podcast_config["if_directory_empty"], last_run_date)
            last_downloaded_file = None
        else:
            current_downloaded_in_feed = [f for f in all_feed_files if f in downloaded_files_set]
            if not current_downloaded_in_feed:
                last_downloaded_file = None
                download_limiter = lambda x: x
            elif podcast_config["fill_up_gaps"]:
                last_downloaded_file = get_last_downloaded_file_before_gap(all_feed_files, current_downloaded_in_feed)
            else:
                last_downloaded_file = current_downloaded_in_feed[-1]
            download_limiter = build_only_new_entities(to_name_function, last_downloaded_file)

        missing_files_links = list(download_limiter(all_feed_entries))
        logger.info('Last downloaded file: "%s"', last_downloaded_file or "<none>")

        if not missing_files_links:
            logger.info('%s: Nothing new to download.', rss_source_name)
            stats.skipped += 1
            return stats

        download_function = partial(download_rss_entity_to_path, podcast_config["http_headers"], to_real_file_name, rss_source_path)

        for rss_entry in reversed(missing_files_links):
            # --- FIX for TypeError: '<=' not supported between instances of 'NoneType' and 'int' ---
            # Ensure downloads_limit is an integer. sys.maxsize is the default.
            # If it comes from configuration and somehow becomes None, default it to sys.maxsize
            current_downloads_limit = global_config.get("downloads_limit", sys.maxsize)
            if current_downloads_limit <= 0: # Now this comparison will always work
                logger.info("Global download limit reached.")
                break
            if podcast_config["download_delay"] > 0:
                time.sleep(podcast_config["download_delay"])

            wanted_file_name = to_real_file_name(rss_entry)

            logger.info('Downloading new episode from "%s"', rss_source_name)
            logger.info('    -> Source URL: "%s"', rss_entry.link)
            logger.info('    -> Saving as: "%s"', wanted_file_name)

            if not dry_run:
                download_function(rss_entry)
                # Decrement the limit only if an actual download was performed
                # Note: `global_config` is a dictionary, so this modifies it directly.
                global_config["downloads_limit"] -= 1

            stats.downloads += 1

    except Exception as e:
        logger.error('Critical failure processing feed "%s": %s', podcast_config.get("name") or podcast_config.get("rss_link"), e)
        stats.errors += 1

    return stats

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        configuration = setup_configuration(args)
    except ConfigurationError as e:
        logger.error("Configuration problem: %s", e)
        return 1

    # Ensure last_run_mark_file_path is passed correctly from configuration
    last_run_datetime = load_the_last_run_date_store_now(
        configuration.get("last_run_mark_file_path"),
        datetime.now()
    )
    dry_run = configuration.get("dry_run", False)
    total_stats = ProcessingStats()

    for rss_source in configuration["podcasts"]:
        podcast_config = merge_parameters_collection(configuration, rss_source)
        stats = process_podcast_feed(
            podcast_config=podcast_config,
            global_config=configuration,
            last_run_date=last_run_datetime,
            dry_run=dry_run,
        )
        total_stats.downloads += stats.downloads
        total_stats.skipped += stats.skipped
        total_stats.errors += stats.errors

    logger.info("Execution summary:")
    logger.info("    Total downloads performed: %d", total_stats.downloads)
    logger.info("    Total feeds skipped: %d", total_stats.skipped)
    logger.info("    Total critical errors: %d", total_stats.errors)

    return 0 if total_stats.errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
