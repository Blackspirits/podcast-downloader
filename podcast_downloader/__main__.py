# podcast_downloader/__main__.py (Final Improved Version)

import os
import re
import sys
import time
import argparse
import logging
from functools import partial
from pathlib import Path
from typing import Callable, Dict, Iterable
from datetime import datetime

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
from .utils import ConsoleOutputFormatter, compose

# Constants
PODCAST_EXTENSIONS = {".mp3": "audio/mpeg"}
USER_AGENT = f"podcast-downloader/1.0 (Python/{sys.version_info.major}.{sys.version_info.minor})"

# Global logger
logger = logging.getLogger("podcast_downloader")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(ConsoleOutputFormatter())
    logger.addHandler(handler)

def download_rss_entity_to_path(
    headers: Dict[str, str],
    to_file_name_function: Callable[[RSSEntity], str],
    path: Path,
    rss_entity: RSSEntity,
):
    """Download an RSS item to the specified path."""
    path.mkdir(parents=True, exist_ok=True)
    path_to_file = path / to_file_name_function(rss_entity)

    try:
        with requests.get(rss_entity.link, headers=headers, stream=True, timeout=30) as response:
            response.raise_for_status()
            with open(path_to_file, "wb") as file:
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)
    except requests.exceptions.RequestException as e:
        logger.error('Network error while downloading "%s": %s', rss_entity.link, e)
    except IOError as e:
        logger.error('Failed to save file "%s": %s', path_to_file, e)
    except Exception:
        logger.exception('Unexpected error downloading "%s" to "%s".', rss_entity.link, path_to_file)

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--downloads_limit", type=int, help="Maximum number of files to download.")
    parser.add_argument("--if_directory_empty", type=str, help="Behavior for empty directories.")
    parser.add_argument("--config", type=str, help="Path to the configuration file.")
    parser.add_argument("--download_delay", type=int, help="Wait time (seconds) between downloads.")
    parser.add_argument("--verbose", action="store_true", help="Enable detailed logging (debug).")
    parser.add_argument("--dry_run", action="store_true", help="Simulate execution without downloading files.")
    return parser

def configuration_to_function_on_empty_directory(
    configuration_value: str, last_run_date: datetime
) -> Callable[[Iterable[RSSEntity]], Iterable[RSSEntity]]:
    if configuration_value == "download_last":
        return partial(only_last_n_entities, 1)
    if configuration_value == "download_all_from_feed":
        return lambda source: source
    if configuration_value == "download_since_last_run":
        if last_run_date:
            return partial(filter, only_entities_from_date(last_run_date))
        logger.error('The option "download_since_last_run" requires "last_run_mark_file_path" configured.')
        raise Exception("Last run marker file missing.")
    local_time = datetime.now()
    if match := re.match(r"^download_from_(\d+)_days$", configuration_value):
        from_date = get_n_age_date(int(match[1]), local_time)
        return partial(filter, only_entities_from_date(from_date))
    if match := re.match(r"^download_last_(\d+)_episodes", configuration_value):
        download_limit = int(match[1])
        return partial(only_last_n_entities, download_limit)
    if match := re.match(r"^download_from_(.*)", configuration_value):
        day_label = parse_day_label(match[1])
        date_func = get_label_to_date(day_label)
        from_date = date_func(local_time)
        return partial(filter, only_entities_from_date(from_date))
    raise Exception(f"The value '{configuration_value}' is not recognized.")

def get_system_file_name_limit(path: Path) -> int:
    # 255 for Windows; 260 - path length for other systems
    return 255 if sys.platform == "win32" else 260 - len(str(path)) - 1

def configuration_to_function_rss_to_name(
    configuration_value: str, sub_configuration: Dict
) -> Callable[[RSSEntity], str]:
    return partial(file_template_to_file_name, configuration_value)

def load_the_last_run_date_store_now(marker_file_path_str: str, now: datetime):
    if not marker_file_path_str:
        return None
    marker_file = Path(marker_file_path_str).expanduser()
    if not marker_file.exists():
        logger.warning("Marker file does not exist. Creating new one (last run date will be now).")
        marker_file.parent.mkdir(parents=True, exist_ok=True)
        marker_file.write_text("Marker file for podcast_downloader.")
        return now
    access_time_stamp = marker_file.stat().st_atime
    access_time = datetime.fromtimestamp(access_time_stamp)
    logger.info("Last script run: %s", access_time.strftime("%Y-%m-%d %H:%M:%S"))
    now_timestamp = time.mktime(now.timetuple())
    os.utime(marker_file, (now_timestamp, now_timestamp))
    return access_time

def main() -> int:
    """Main function executing the downloader logic."""
    DEFAULT_CONFIGURATION = {
        "downloads_limit": sys.maxsize,
        "if_directory_empty": "download_last",
        "podcast_extensions": PODCAST_EXTENSIONS,
        "file_name_template": "%title%.%file_extension%",
        "http_headers": {"User-Agent": USER_AGENT},
        "fill_up_gaps": False,
        "download_delay": 0,
        "last_run_mark_file_path": None,
        "podcasts": [],
    }

    parser = build_parser()
    PARAMETERS_CONFIGURATION = parse_argv(parser)
    
    # Adjust logging level if verbose
    if PARAMETERS_CONFIGURATION.get("verbose"):
        logger.setLevel(logging.DEBUG)
        logger.debug("Detailed logging enabled (--verbose).")

    config_file_name = PARAMETERS_CONFIGURATION.get("config", "~/.podcast_downloader_config.json")
    config_path = Path(config_file_name).expanduser()
    logger.info('Loading configuration file: "%s"', config_path)
    try:
        CONFIGURATION_FROM_FILE = load_configuration_file(config_path)
    except (FileNotFoundError, ValueError) as e:
        logger.warning("Could not load configuration file: %s. Using defaults.", e)
        CONFIGURATION_FROM_FILE = {}

    CONFIGURATION = merge_parameters_collection(DEFAULT_CONFIGURATION, CONFIGURATION_FROM_FILE, PARAMETERS_CONFIGURATION)
    try:
        configuration_verification(CONFIGURATION)
    except ConfigurationError as e:
        logger.error("Configuration problem: %s", e)
        return 1

    RSS_SOURCES = CONFIGURATION["podcasts"]
    DOWNLOADS_LIMITS = CONFIGURATION["downloads_limit"]
    LAST_RUN_DATETIME = load_the_last_run_date_store_now(CONFIGURATION["last_run_mark_file_path"], datetime.now())
    dry_run = PARAMETERS_CONFIGURATION.get("dry_run", False)

    total_downloads = 0
    total_skipped = 0
    total_errors = 0

    for rss_source in RSS_SOURCES:
        try:
            rss_source_name = rss_source.get("name", None)
            rss_source_path = Path(rss_source["path"]).expanduser()
            rss_source_link = rss_source["rss_link"]

            if rss_source.get("disable", False):
                logger.info('Skipping "%s" (disabled in configuration).', rss_source_name or rss_source_link)
                total_skipped += 1
                continue

            feed = load_feed(rss_source_link)
            if feed.bozo and not feed.entries:
                logger.error('Error accessing link "%s": %s', rss_source_link, feed.bozo_exception)
                total_errors += 1
                continue

            if not rss_source_name:
                rss_source_name = get_feed_title_from_feed(feed)
            logger.info('Checking "%s"', rss_source_name)

            # Specific podcast config
            podcast_config = merge_parameters_collection(CONFIGURATION, rss_source)

            to_name_function = configuration_to_function_rss_to_name(podcast_config["file_name_template"], rss_source)
            file_length_limit = get_system_file_name_limit(rss_source_path)
            to_real_podcast_file_name = compose(partial(limit_file_name, file_length_limit), to_name_function)

            extensions_checker = get_extensions_checker(podcast_config["podcast_extensions"].keys())
            downloaded_files = list(get_downloaded_files(extensions_checker, rss_source_path))
            allow_link_types = list(set(podcast_config["podcast_extensions"].values()))

            all_feed_entries = list(filter(
                build_only_allowed_filter_for_link_data(allow_link_types),
                flatten_rss_links_data(get_raw_rss_entries_from_feed(feed))
            ))

            all_feed_files = [to_real_podcast_file_name(entry) for entry in all_feed_entries][::-1]
            downloaded_files_set = set(downloaded_files)

            if not downloaded_files_set:
                download_limiter = configuration_to_function_on_empty_directory(podcast_config["if_directory_empty"], LAST_RUN_DATETIME)
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
                logger.info('%s: No new episodes to download.', rss_source_name)
                total_skipped += 1
                continue

            download_podcast = partial(download_rss_entity_to_path, podcast_config["http_headers"], to_real_podcast_file_name, rss_source_path)

            for rss_entry in reversed(missing_files_links):
                if DOWNLOADS_LIMITS <= 0:
                    logger.info("Global downloads limit reached.")
                    break

                if podcast_config["download_delay"] > 0:
                    logger.debug("Waiting %d seconds before next download.", podcast_config["download_delay"])
                    time.sleep(podcast_config["download_delay"])

                wanted_podcast_file_name = to_real_podcast_file_name(rss_entry)

                logger.info('Downloading new episode from: %s', rss_source_name)
                logger.info('    -> Source URL: "%s"', rss_entry.link)
                logger.info('    -> Saving as: "%s"', wanted_podcast_file_name)

                if not dry_run:
                    download_podcast(rss_entry)
                    total_downloads += 1
                else:
                    logger.info("[Dry-run] Simulated: file '%s' will not be downloaded.", wanted_podcast_file_name)

                DOWNLOADS_LIMITS -= 1

        except Exception:
            logger.exception('Critical failure processing feed "%s".', rss_source.get('name', rss_source.get('rss_link')))
            total_errors += 1

    logger.info("Execution summary:")
    logger.info("    Total downloads performed: %d", total_downloads)
    logger.info("    Total feeds skipped: %d", total_skipped)
    logger.info("    Total critical errors: %d", total_errors)

    return 0

if __name__ == "__main__":
    sys.exit(main())
