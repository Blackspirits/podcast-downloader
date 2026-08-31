import os
import shutil
from typing import Callable, Dict, Iterable, List, Tuple
import urllib
import argparse
import re
import time
import sys

from functools import partial
from . import configuration

from podcast_downloader.configuration import (
    configuration_verification,
    get_label_to_date,
    get_n_age_date,
    parse_day_label,
)
from .utils import ConsoleOutputFormatter, compose
from .downloaded import get_downloaded_files, get_extensions_checker
from .filenames import (
    finalize_file_name,
    get_file_name_limit,
    safe_destination_path,
)
from .parameters import merge_parameters_collection, load_configuration_file, parse_argv
from .rss import (
    RSSEntity,
    build_only_allowed_filter_for_link_data,
    flatten_rss_links_data,
    get_feed_title_from_feed,
    get_raw_rss_entries_from_feed,
    load_feed,
    only_entities_from_date,
    only_last_n_entities,
    raw_file_template_to_file_name,
)
from .state import episode_identity, get_episode, load_state, mark_episode, save_state


DOWNLOAD_TIMEOUT_SECONDS = 30
DOWNLOAD_CHUNK_SIZE = 1024 * 1024
REJECTED_CONTENT_TYPES = {"text/html", "application/json"}


def download_rss_entity_to_path(
    headers: List[Tuple[str, str]],
    to_file_name_function: Callable[[RSSEntity], str],
    path: str,
    rss_entity: RSSEntity,
) -> bool:
    path_to_file = safe_destination_path(path, to_file_name_function(rss_entity))
    path_to_partial_file = path_to_file + ".part"

    try:
        request = urllib.request.Request(rss_entity.link, headers=headers)

        with urllib.request.urlopen(
            request, timeout=DOWNLOAD_TIMEOUT_SECONDS
        ) as response:
            content_type = response.headers.get_content_type()
            if content_type in REJECTED_CONTENT_TYPES:
                raise ValueError(
                    'Unexpected content type "%s" for podcast file' % content_type
                )

            expected_length = response.headers.get("Content-Length")

            with open(path_to_partial_file, "wb") as file:
                shutil.copyfileobj(response, file, length=DOWNLOAD_CHUNK_SIZE)

            if expected_length is not None:
                actual_length = os.path.getsize(path_to_partial_file)
                if actual_length != int(expected_length):
                    raise IOError(
                        "Downloaded file size does not match the Content-Length header"
                    )

        os.replace(path_to_partial_file, path_to_file)
        return True

    except Exception:
        if os.path.exists(path_to_partial_file):
            os.remove(path_to_partial_file)

        logger.exception(
            'The podcast file "%s" could not be saved to disk "%s" due to the following error',
            rss_entity.link,
            path_to_file,
        )
        return False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--downloads_limit",
        required=False,
        type=int,
        help="The maximum number of mp3 files which script will download",
    )

    parser.add_argument(
        "--if_directory_empty",
        required=False,
        type=str,
        help="The general approach on empty directory",
    )

    parser.add_argument(
        "--config",
        required=False,
        type=str,
        help="The path to configuration file",
    )

    parser.add_argument(
        "--download_delay",
        required=False,
        type=int,
        help="The waiting time (seconds) between downloads",
    )

    return parser


def configuration_to_function_on_empty_directory(
    configuration_value: str, last_run_date: time.struct_time
) -> Callable[[Iterable[RSSEntity]], Iterable[RSSEntity]]:
    if configuration_value == "download_last":
        return partial(only_last_n_entities, 1)

    if configuration_value == "download_all_from_feed":
        return lambda source: source

    if configuration_value == "download_since_last_run":
        if last_run_date:
            return only_entities_from_date(last_run_date)

        logger.error(
            'The "download_since_last_run" require setup the "last_run_mark_file_path"'
        )
        raise Exception("Missing the last run mark file")

    local_time = time.localtime()

    from_n_day_match = re.match(r"^download_from_(\d+)_days$", configuration_value)
    if from_n_day_match:
        from_date = get_n_age_date(int(from_n_day_match[1]), local_time)
        return only_entities_from_date(from_date)

    last_n_episodes = re.match(r"^download_last_(\d+)_episodes", configuration_value)
    if last_n_episodes:
        download_limit = int(last_n_episodes[1])
        return partial(only_last_n_entities, download_limit)

    from_nth_day_match = re.match(r"^download_from_(.*)", configuration_value)
    if from_nth_day_match:
        day_label = parse_day_label(from_nth_day_match[1])

        return only_entities_from_date(get_label_to_date(day_label)(local_time))

    raise Exception(f"The value the '{configuration_value}' is not recognizable")


def is_windows_running():
    return sys.platform == "win32"


def get_system_file_name_limit(sub_configuration: Dict[str, str]) -> int:
    return get_file_name_limit(os.path.expanduser(sub_configuration["path"]))


def configuration_to_function_rss_to_name(
    configuration_value: str, sub_configuration: Dict[str, str]
) -> Callable[[RSSEntity], str]:
    if (
        configuration.CONFIG_PODCASTS_REQUIRE_DATE in sub_configuration
        and configuration.CONFIG_FILE_NAME_TEMPLATE not in sub_configuration
    ):
        default_file_name_template_with_date = (
            "[%publish_date%] %file_name%.%file_extension%"
        )

        if sub_configuration[configuration.CONFIG_PODCASTS_REQUIRE_DATE]:
            configuration_value = default_file_name_template_with_date

        logger.warning(
            'The option %s is deprecated, please replace use of it with the %s option: "%s"',
            configuration.CONFIG_PODCASTS_REQUIRE_DATE,
            configuration.CONFIG_FILE_NAME_TEMPLATE,
            default_file_name_template_with_date,
        )

    return partial(raw_file_template_to_file_name, configuration_value)


def load_the_last_run_date_store_now(marker_file_path, now):
    if marker_file_path == None:
        return None

    full_marker_file_path = os.path.expanduser(marker_file_path)
    if not os.path.exists(full_marker_file_path):
        logger.warning("Marker file doesn't exist, creating (set last time run as now)")

        with open(marker_file_path, "w") as file:
            file.write(
                "This is a marker file for podcast_download. It last access date is used to determine the last run time"
            )

        return now

    access_time = time.localtime(os.path.getatime(full_marker_file_path))
    logger.info(
        "Last time the script has been run: %s",
        time.strftime("%Y-%m-%d %H:%M:%S", access_time),
    )

    os.utime(full_marker_file_path, times=(time.mktime(now), time.mktime(now)))
    return access_time


def bootstrap_episode_state(
    state: dict,
    entries: List[RSSEntity],
    downloaded_files: Iterable[str],
    to_file_name_function: Callable[[RSSEntity], str],
    feed_url: str,
) -> bool:
    downloaded_files = set(downloaded_files)
    changed = False

    for entry in entries:
        identity = episode_identity(entry, feed_url)
        if get_episode(state, identity) is not None:
            continue

        file_name = to_file_name_function(entry)
        if file_name in downloaded_files:
            mark_episode(state, identity, entry, file_name)
            changed = True

    return changed


def is_episode_present(
    state: dict,
    entry: RSSEntity,
    downloaded_files: Iterable[str],
    feed_url: str,
    fill_up_gaps: bool,
) -> bool:
    record = get_episode(state, episode_identity(entry, feed_url))
    if record is None:
        return False

    if not fill_up_gaps:
        return True

    return record.get("filename") in downloaded_files


def find_state_boundary(
    state: dict,
    entries: List[RSSEntity],
    downloaded_files: Iterable[str],
    feed_url: str,
    fill_up_gaps: bool,
):
    downloaded_files = set(downloaded_files)

    if not fill_up_gaps:
        return next(
            (
                entry
                for entry in entries
                if is_episode_present(
                    state, entry, downloaded_files, feed_url, fill_up_gaps
                )
            ),
            None,
        )

    last_present = None
    for entry in reversed(entries):
        if is_episode_present(
            state, entry, downloaded_files, feed_url, fill_up_gaps
        ):
            last_present = entry
        elif last_present is not None:
            return last_present

    return last_present


def select_missing_entries(
    state: dict,
    entries: List[RSSEntity],
    downloaded_files: Iterable[str],
    feed_url: str,
    fill_up_gaps: bool,
    on_empty_directory: Callable[[Iterable[RSSEntity]], Iterable[RSSEntity]],
) -> Tuple[List[RSSEntity], RSSEntity]:
    downloaded_files = set(downloaded_files)
    boundary = find_state_boundary(
        state, entries, downloaded_files, feed_url, fill_up_gaps
    )

    if boundary is None:
        return list(on_empty_directory(entries)), None

    boundary_identity = episode_identity(boundary, feed_url)
    missing = []
    for entry in entries:
        if episode_identity(entry, feed_url) == boundary_identity:
            break

        if not is_episode_present(
            state, entry, downloaded_files, feed_url, fill_up_gaps
        ):
            missing.append(entry)

    return missing, boundary


if __name__ == "__main__":
    import sys
    from logging import getLogger, StreamHandler, INFO

    logger = getLogger(__name__)
    logger.setLevel(INFO)
    stdout_handler = StreamHandler(stream=sys.stdout)
    stdout_handler.setFormatter(ConsoleOutputFormatter())
    logger.addHandler(stdout_handler)

    DEFAULT_CONFIGURATION = {
        configuration.CONFIG_DOWNLOADS_LIMIT: sys.maxsize,
        configuration.CONFIG_IF_DIRECTORY_EMPTY: "download_last",
        configuration.CONFIG_PODCAST_EXTENSIONS: {".mp3": "audio/mpeg"},
        configuration.CONFIG_FILE_NAME_TEMPLATE: "%file_name%.%file_extension%",
        configuration.CONFIG_HTTP_HEADER: {"User-Agent": "podcast-downloader"},
        configuration.CONFIG_FILL_UP_GAPS: False,
        configuration.CONFIG_DOWNLOAD_DELAY: 0,
        configuration.CONFIG_LAST_RUN_MARK_PATH: None,
        configuration.CONFIG_PODCASTS: [],
    }

    PARAMETERS_CONFIGURATION = parse_argv(build_parser())

    config_file_name = PARAMETERS_CONFIGURATION.get(
        "config", "~/.podcast_downloader_config.json"
    )
    logger.info('Loading configuration (from file: "%s")', config_file_name)
    CONFIGURATION_FROM_FILE = load_configuration_file(
        os.path.expanduser(config_file_name)
    )

    CONFIGURATION = merge_parameters_collection(
        DEFAULT_CONFIGURATION,
        CONFIGURATION_FROM_FILE,
        PARAMETERS_CONFIGURATION,
    )

    is_valid, error = configuration_verification(CONFIGURATION)
    if not is_valid:
        logger.info("There is a problem with configuration file: %s", error)
        exit(1)

    RSS_SOURCES = CONFIGURATION[configuration.CONFIG_PODCASTS]
    DOWNLOADS_LIMITS = CONFIGURATION[configuration.CONFIG_DOWNLOADS_LIMIT]
    LAST_RUN_DATETIME = load_the_last_run_date_store_now(
        CONFIGURATION[configuration.CONFIG_LAST_RUN_MARK_PATH], time.localtime()
    )

    for rss_source in RSS_SOURCES:
        rss_source_name = rss_source.get(configuration.CONFIG_PODCASTS_NAME, None)
        rss_source_path = os.path.expanduser(
            rss_source[configuration.CONFIG_PODCASTS_PATH]
        )
        file_length_limit = get_system_file_name_limit(rss_source)
        rss_source_link = rss_source[configuration.CONFIG_PODCASTS_RSS_LINK]
        rss_disable = rss_source.get(configuration.CONFIG_PODCASTS_DISABLE, False)
        rss_file_name_template_value = rss_source.get(
            configuration.CONFIG_FILE_NAME_TEMPLATE,
            CONFIGURATION[configuration.CONFIG_FILE_NAME_TEMPLATE],
        )
        rss_on_empty_directory = rss_source.get(
            configuration.CONFIG_IF_DIRECTORY_EMPTY,
            CONFIGURATION[configuration.CONFIG_IF_DIRECTORY_EMPTY],
        )
        rss_podcast_extensions = rss_source.get(
            configuration.CONFIG_PODCAST_EXTENSIONS,
            CONFIGURATION[configuration.CONFIG_PODCAST_EXTENSIONS],
        )
        rss_https_header = merge_parameters_collection(
            CONFIGURATION[configuration.CONFIG_HTTP_HEADER],
            rss_source.get(configuration.CONFIG_HTTP_HEADER, {}),
        )
        rss_fill_up_gaps = rss_source.get(
            CONFIGURATION[configuration.CONFIG_FILL_UP_GAPS],
            rss_source.get(configuration.CONFIG_FILL_UP_GAPS, False),
        )
        rss_download_delay = rss_source.get(
            CONFIGURATION[configuration.CONFIG_DOWNLOAD_DELAY],
            rss_source.get(configuration.CONFIG_DOWNLOAD_DELAY, 0),
        )

        if rss_disable:
            logger.info('Skipping the "%s"', rss_source_name or rss_source_link)
            continue

        feed = load_feed(rss_source_link)
        if feed.bozo and len(feed.entries) == 0:
            logger.error(
                f"Error while checking the link: '{rss_source_link}': {feed['bozo_exception']}"
            )
            continue

        if not rss_source_name:
            rss_source_name = get_feed_title_from_feed(feed)

        logger.info('Checking "%s"', rss_source_name)

        to_name_function = configuration_to_function_rss_to_name(
            rss_file_name_template_value, rss_source
        )

        on_empty_directory = configuration_to_function_on_empty_directory(
            rss_on_empty_directory, LAST_RUN_DATETIME
        )

        downloaded_files = list(
            get_downloaded_files(
                get_extensions_checker(rss_podcast_extensions), rss_source_path
            )
        )

        allow_link_types = list(set(rss_podcast_extensions.values()))

        all_feed_entries = compose(
            list,
            partial(filter, build_only_allowed_filter_for_link_data(allow_link_types)),
            flatten_rss_links_data,
            get_raw_rss_entries_from_feed,
        )(feed)

        def to_real_podcast_file_name(entry: RSSEntity) -> str:
            raw_file_name = to_name_function(entry)
            return finalize_file_name(
                raw_file_name,
                file_length_limit,
                episode_identity(entry, rss_source_link),
            )

        episode_state = load_state(rss_source_path)
        if bootstrap_episode_state(
            episode_state,
            all_feed_entries,
            downloaded_files,
            to_real_podcast_file_name,
            rss_source_link,
        ):
            save_state(rss_source_path, episode_state)

        missing_files_links, boundary = select_missing_entries(
            episode_state,
            all_feed_entries,
            downloaded_files,
            rss_source_link,
            rss_fill_up_gaps,
            on_empty_directory,
        )

        if boundary is None:
            last_downloaded_file = None
        else:
            boundary_record = get_episode(
                episode_state, episode_identity(boundary, rss_source_link)
            )
            last_downloaded_file = (
                boundary_record.get("filename")
                if boundary_record
                else to_real_podcast_file_name(boundary)
            )

        logger.info('Last downloaded file "%s"', last_downloaded_file or "<none>")

        if missing_files_links:
            download_podcast = partial(
                download_rss_entity_to_path,
                rss_https_header,
                to_real_podcast_file_name,
            )

            first_element = True
            for rss_entry in reversed(missing_files_links):
                if rss_download_delay > 0:
                    if not first_element:
                        logger.info(
                            "The download is sleeping (%d second)", rss_download_delay
                        )
                        time.sleep(rss_download_delay)
                        first_element = False

                if DOWNLOADS_LIMITS == 0:
                    continue

                real_podcast_file_name = to_real_podcast_file_name(rss_entry)
                wanted_podcast_file_name = to_name_function(rss_entry)

                if real_podcast_file_name != wanted_podcast_file_name:
                    logger.info(
                        'The podcast file name "%s" was adjusted to "%s" for filesystem compatibility',
                        wanted_podcast_file_name,
                        real_podcast_file_name,
                    )

                logger.info(
                    '%s: Downloading file: "%s" saved as "%s"',
                    rss_source_name,
                    rss_entry.link,
                    real_podcast_file_name,
                )

                if download_podcast(rss_source_path, rss_entry):
                    identity = episode_identity(rss_entry, rss_source_link)
                    mark_episode(
                        episode_state, identity, rss_entry, real_podcast_file_name
                    )
                    save_state(rss_source_path, episode_state)
                    downloaded_files.append(real_podcast_file_name)
                    DOWNLOADS_LIMITS -= 1
        else:
            logger.info("%s: Nothing new", rss_source_name)

    logger.info("Finished")
