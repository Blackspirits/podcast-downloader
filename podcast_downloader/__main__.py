import os
import re
import sys
import time
import argparse
import logging
from functools import partial
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Tuple
from datetime import datetime

import requests

from . import configuration
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

# Single, global logger configuration
logger = logging.getLogger("podcast_downloader")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(ConsoleOutputFormatter())
    logger.addHandler(handler)

def sanitize_filename(filename: str) -> str:
    """Remove illegal characters from a filename."""
    return re.sub(r'[\\/*?:"<>|]', "", filename)

def download_rss_entity_to_path(
    headers: Dict[str, str],
    to_file_name_function: Callable[[RSSEntity], str],
    path: Path,
    rss_entity: RSSEntity,
):
    """Downloads an RSS entity to a path, using requests and pathlib."""
    path.mkdir(parents=True, exist_ok=True)
    
    path_to_file = path / to_file_name_function(rss_entity)

    try:
        with requests.get(rss_entity.link, headers=headers, stream=True, timeout=30) as response:
            response.raise_for_status()
            with open(path_to_file, "wb") as file:
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)

    except requests.exceptions.RequestException as e:
        logger.error('Network error while trying to download "{}": {}', rss_entity.link, e)
    except IOError as e:
        logger.error('Failed to save file "{}" to disk: {}', path_to_file, e)
    except Exception as e:
        logger.exception('An unexpected error occurred while downloading "{}" to "{}".', rss_entity.link, path_to_file)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--downloads_limit", type=int, help="The maximum number of files the script will download.")
    parser.add_argument("--if_directory_empty", type=str, help="The general approach for empty directories.")
    parser.add_argument("--config", type=str, help="The path to the configuration file.")
    parser.add_argument("--download_delay", type=int, help="The waiting time (in seconds) between downloads.")
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
        logger.error('The "download_since_last_run" option requires "last_run_mark_file_path" to be set')
        raise Exception("Missing last run marker file")

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

    raise Exception(f"The value '{configuration_value}' is not recognizable")


def is_windows_running():
    return sys.platform == "win32"


def get_system_file_name_limit(sub_configuration: Dict) -> int:
    path_str = str(sub_configuration["path"])
    return 255 if is_windows_running() else 260 - len(path_str) - 1


def configuration_to_function_rss_to_name(
    configuration_value: str, sub_configuration: Dict
) -> Callable[[RSSEntity], str]:
    if (
        configuration.CONFIG_PODCASTS_REQUIRE_DATE in sub_configuration
        and configuration.CONFIG_FILE_NAME_TEMPLATE not in sub_configuration
    ):
        default_template = "[%publish_date:%Y-%m-%d%] %title%.%file_extension%"
        if sub_configuration[configuration.CONFIG_PODCASTS_REQUIRE_DATE]:
            configuration_value = default_template
        logger.warning(
            'The option {} is deprecated. Please use {}: "{}"',
            configuration.CONFIG_PODCASTS_REQUIRE_DATE,
            configuration.CONFIG_FILE_NAME_TEMPLATE,
            default_template,
        )
    
    return compose(
        sanitize_filename,
        partial(file_template_to_file_name, configuration_value)
    )


def load_the_last_run_date_store_now(marker_file_path_str: str, now: datetime):
    if not marker_file_path_str:
        return None

    marker_file = Path(marker_file_path_str).expanduser()
    
    if not marker_file.exists():
        logger.warning("Marker file does not exist, creating a new one (last run time will be set to now).")
        marker_file.parent.mkdir(parents=True, exist_ok=True)
        marker_file.write_text(
            "This is a marker file for podcast_downloader. Its last access date is used to determine the last run time."
        )
        return now

    access_time_stamp = marker_file.stat().st_atime
    access_time = datetime.fromtimestamp(access_time_stamp)
    logger.info(
        "The last time the script was run: {}",
        access_time.strftime("%Y-%m-%d %H:%M:%S"),
    )

    now_timestamp = time.mktime(now.timetuple())
    os.utime(marker_file, (now_timestamp, now_timestamp))
    return access_time


def main():
    """Main function that runs the downloader logic."""
    DEFAULT_CONFIGURATION = {
        configuration.CONFIG_DOWNLOADS_LIMIT: sys.maxsize,
        configuration.CONFIG_IF_DIRECTORY_EMPTY: "download_last",
        configuration.CONFIG_PODCAST_EXTENSIONS: {".mp3": "audio/mpeg"},
        configuration.CONFIG_FILE_NAME_TEMPLATE: "%file_name%.%file_extension%",
        configuration.CONFIG_HTTP_HEADER: {"User-Agent": f"podcast-downloader/1.0 (Python/{sys.version_info.major}.{sys.version_info.minor})"},
        configuration.CONFIG_FILL_UP_GAPS: False,
        configuration.CONFIG_DOWNLOAD_DELAY: 0,
        configuration.CONFIG_LAST_RUN_MARK_PATH: None,
        configuration.CONFIG_PODCASTS: [],
    }

    PARAMETERS_CONFIGURATION = parse_argv(build_parser())
    config_file_name = PARAMETERS_CONFIGURATION.get("config", "~/.podcast_downloader_config.json")
    
    config_path = Path(config_file_name).expanduser()
    logger.info('Loading configuration from file: "{}"', config_path)
    
    try:
        CONFIGURATION_FROM_FILE = load_configuration_file(config_path)
    except (FileNotFoundError, ValueError) as e:
        logger.warning("Could not load configuration file: {}. Continuing with defaults.", e)
        CONFIGURATION_FROM_FILE = {}


    CONFIGURATION = merge_parameters_collection(
        DEFAULT_CONFIGURATION, CONFIGURATION_FROM_FILE, PARAMETERS_CONFIGURATION
    )

    try:
        configuration_verification(CONFIGURATION)
    except ConfigurationError as e:
        logger.error("There is a problem with the configuration: {}", e)
        sys.exit(1)

    RSS_SOURCES = CONFIGURATION[configuration.CONFIG_PODCASTS]
    DOWNLOADS_LIMITS = CONFIGURATION[configuration.CONFIG_DOWNLOADS_LIMIT]
    LAST_RUN_DATETIME = load_the_last_run_date_store_now(
        CONFIGURATION[configuration.CONFIG_LAST_RUN_MARK_PATH], datetime.now()
    )

    for rss_source in RSS_SOURCES:
        try:
            rss_source_name = rss_source.get(configuration.CONFIG_PODCASTS_NAME, None)
            rss_source_path = Path(rss_source[configuration.CONFIG_PODCASTS_PATH]).expanduser()
            rss_source_link = rss_source[configuration.CONFIG_PODCASTS_RSS_LINK]
            
            if rss_source.get(configuration.CONFIG_PODCASTS_DISABLE, False):
                logger.info('Skipping "{}" (disabled in config)', rss_source_name or rss_source_link)
                continue

            feed = load_feed(rss_source_link)
            if feed.bozo and not feed.entries:
                logger.error("Error while checking link: '{}': {}", rss_source_link, feed.bozo_exception)
                continue

            if not rss_source_name:
                rss_source_name = get_feed_title_from_feed(feed)
            logger.info('Checking "{}"', rss_source_name)
            
            rss_file_name_template_value = rss_source.get(configuration.CONFIG_FILE_NAME_TEMPLATE, CONFIGURATION[configuration.CONFIG_FILE_NAME_TEMPLATE])
            rss_on_empty_directory = rss_source.get(configuration.CONFIG_IF_DIRECTORY_EMPTY, CONFIGURATION[configuration.CONFIG_IF_DIRECTORY_EMPTY])
            rss_podcast_extensions = rss_source.get(configuration.CONFIG_PODCAST_EXTENSIONS, CONFIGURATION[configuration.CONFIG_PODCAST_EXTENSIONS])
            rss_https_header = merge_parameters_collection(CONFIGURATION[configuration.CONFIG_HTTP_HEADER], rss_source.get(configuration.CONFIG_HTTP_HEADER, {}))
            rss_fill_up_gaps = rss_source.get(configuration.CONFIG_FILL_UP_GAPS, False)
            rss_download_delay = rss_source.get(configuration.CONFIG_DOWNLOAD_DELAY, CONFIGURATION[configuration.CONFIG_DOWNLOAD_DELAY])

            to_name_function = configuration_to_function_rss_to_name(rss_file_name_template_value, rss_source)
            file_length_limit = get_system_file_name_limit({"path": rss_source_path})
            to_real_podcast_file_name = compose(partial(limit_file_name, file_length_limit), to_name_function)

            downloaded_files = list(get_downloaded_files(get_extensions_checker(rss_podcast_extensions.keys()), rss_source_path))
            allow_link_types = list(set(rss_podcast_extensions.values()))
            all_feed_entries = list(flatten_rss_links_data(get_raw_rss_entries_from_feed(feed)))
            all_feed_entries = list(filter(build_only_allowed_filter_for_link_data(allow_link_types), all_feed_entries))
            
            all_feed_files = [to_real_podcast_file_name(entry) for entry in all_feed_entries][::-1]
            downloaded_files_set = set(downloaded_files)
            
            if not downloaded_files_set:
                download_limiter = configuration_to_function_on_empty_directory(rss_on_empty_directory, LAST_RUN_DATETIME)
                last_downloaded_file = None
            else:
                current_downloaded_in_feed = [f for f in all_feed_files if f in downloaded_files_set]
                if not current_downloaded_in_feed:
                    last_downloaded_file = None
                    download_limiter = lambda x: x # Download all rss_source_name = rss_source.ge
                elif rss_fill_up_gaps:
                    last_downloaded_file = get_last_downloaded_file_before_gap(all_feed_files, current_downloaded_in_feed)
                else:
                    last_downloaded_file = current_downloaded_in_feed[-1]
                download_limiter = build_only_new_entities(to_name_function, last_downloaded_file)

            missing_files_links = list(download_limiter(all_feed_entries))
            logger.info('Last downloaded file: "{}"', last_downloaded_file or "<none>")

            if not missing_files_links:
                logger.info("{}: Nothing new.", rss_source_name)
                continue
            
            download_podcast = partial(download_rss_entity_to_path, rss_https_header, to_real_podcast_file_name, rss_source_path)

            first_element = True
            for rss_entry in reversed(missing_files_links):
                if DOWNLOADS_LIMITS <= 0:
                    logger.info("Global download limit reached.")
                    break

                if rss_download_delay > 0 and not first_element:
                    logger.info("Waiting {} second(s) before next download...", rss_download_delay)
                    time.sleep(rss_download_delay)
                first_element = False

                wanted_podcast_file_name = to_real_podcast_file_name(rss_entry)
                
                # Replaced the single log line with three separate, clearer lines.
                logger.info('{}: Downloading file:', rss_source_name)
                logger.info('    -> Source URL: "{}"', rss_entry.link)
                logger.info('    -> Saved as: "{}"', wanted_podcast_file_name)

                download_podcast(rss_entry)
                DOWNLOADS_LIMITS -= 1
        
        except Exception as e:
            logger.error('Critical failure while processing feed "{}". Error: {}', rss_source.get('name', rss_source.get('rss_link')), e)


if __name__ == "__main__":
    main()
    logger.info("Finished.")
