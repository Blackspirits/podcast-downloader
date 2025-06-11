import os
from typing import Callable, Dict, Iterable, List, Tuple
import urllib
import argparse
import re
import time
import sys
import urllib.error # I added this import

from functools import partial
from . import configuration 

from podcast_downloader.configuration import (
    configuration_verification,
    get_label_to_date,
    get_n_age_date,
    parse_day_label,
)
from .utils import ConsoleOutputFormatter, compose
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

from logging import getLogger, StreamHandler, INFO

def ascii_clear():
    os.system('cls' if os.name == 'nt' else 'clear')
    print("""    
ooooooooo.                   .o8                                   .                                        
`888   `Y88.                "888                                 .o8                                        
 888   .d88'  .ooooo.   .oooo888   .ooooo.   .oooo.    .oooo.o .o888oo                                      
 888ooo88P'  d88' `88b d88' `888  d88' `"Y8 `P  )88b  d88(  "8   888                                        
 888         888   888 888   888  888        .oP"888  `"Y88b.    888                                        
 888         888   888 888   888  888   .o8 d8(  888  o.  )88b   888 .                                      
o888o        `Y8bod8P' `Y8bod88P" `Y8bod8P' `Y888""8o 8""888P'   "888"                                      
                                                                                                            
oooooooooo.                                          oooo                            .o8                    
`888'   `Y8b                                         `888                           "888                    
 888      888  .ooooo.  oooo oooo    ooo ooo. .oo.    888   .ooooo.   .oooo.    .oooo888   .ooooo.  oooo d8b
 888      888 d88' `88b  `88. `88.  .8'  `888P"Y88b   888  d88' `88b `P  )88b  d88' `888  d88' `88b `888""8P
 888      888 888   888   `88..]88..8'    888   888   888  888   888  .oP"888  888   888  888ooo888  888    
 888     d88' 888   888    `888'`888'     888   888   888  888   888 d8(  888  888   888  888    .o  888    
o888bood8P'   `Y8bod8P'     `8'  `8'     o888o o888o o888o `Y8bod8P' `Y888""8o `Y8bod88P" `Y8bod8P' d888b   

                                     dplocki / BlackSpirits 2025

""")
    time.sleep(2)

    if __name__ == "__main__":
        main()
        
    logger = getLogger(__name__)
    logger.setLevel(INFO)
    stdout_handler = StreamHandler(stream=sys.stdout)
    stdout_handler.setFormatter(ConsoleOutputFormatter())
    logger.addHandler(stdout_handler)

def download_rss_entity_to_path(
    headers: List[Tuple[str, str]],
    to_file_name_function: Callable[[RSSEntity], str],
    path: str,
    rss_entity: RSSEntity,
):
    path_to_file = os.path.join(path, to_file_name_function(rss_entity))

    try:
        request = urllib.request.Request(rss_entity.link, headers=headers)

        with urllib.request.urlopen(request) as response:
            with open(path_to_file, "wb") as file:
                file.write(response.read())

    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        logger.exception(
            'Failed to download podcast file "%s" due to network or HTTP error: %s',
            rss_entity.link,
            e
        )
    except IOError as e: # For disk write errors
        logger.exception(
            'Could not save podcast file "%s" to disk "%s" due to I/O error: %s',
            rss_entity.link,
            path_to_file,
            e
        )
    except Exception: # Keeps a generic capture as a fallback for unexpected errorsFor disk write errors
        logger.exception(
            'An unexpected error occurred while downloading/saving podcast file "%s" to disk "%s"',
            rss_entity.link,
            path_to_file,
        )


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
    # on Windows, the file name is limited to 260 characters including the path to it
    return 255 if is_windows_running() else 260 - len(sub_configuration["path"]) - 1


def configuration_to_function_rss_to_name(
    configuration_value: str, sub_configuration: Dict[str, str]
) -> Callable[[RSSEntity], str]:

    return partial(file_template_to_file_name, configuration_value)


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
        file_length_limit = get_system_file_name_limit(rss_source)
        rss_source_name = rss_source.get(configuration.CONFIG_PODCASTS_NAME, None)
        rss_source_path = os.path.expanduser(
            rss_source[configuration.CONFIG_PODCASTS_PATH]
        )
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
            configuration.CONFIG_FILL_UP_GAPS, # Try getting it from rss_source
            CONFIGURATION[configuration.CONFIG_FILL_UP_GAPS], # Fallback to global configuration
        )
        rss_download_delay = rss_source.get(
            configuration.CONFIG_DOWNLOAD_DELAY,
            CONFIGURATION[configuration.CONFIG_DOWNLOAD_DELAY],
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

        to_real_podcast_file_name = compose(
            partial(limit_file_name, file_length_limit), to_name_function
        )

        all_feed_files = list(map(to_real_podcast_file_name, all_feed_entries))[::-1]
        downloaded_files = [feed for feed in all_feed_files if feed in downloaded_files]

        last_downloaded_file = None
        if downloaded_files:
            if rss_fill_up_gaps:
                last_downloaded_file = get_last_downloaded_file_before_gap(
                    all_feed_files, downloaded_files
                )
            else:
                last_downloaded_file = downloaded_files[-1]

            download_limiter_function = partial(
                build_only_new_entities(to_name_function), last_downloaded_file
            )
        else:
            download_limiter_function = on_empty_directory

        missing_files_links = compose(list, download_limiter_function)(all_feed_entries)

        logger.info('Last downloaded file "%s"', last_downloaded_file or "<none>")

        if missing_files_links:
            download_podcast = partial(
                download_rss_entity_to_path,
                rss_https_header,
                to_real_podcast_file_name,
            )

            first_element = True
            for rss_entry in reversed(missing_files_links):
                if rss_download_delay > 0 and not first_element: # Sleep only if there is a delay and it is not the first element
                    logger.info(
                        "The download is sleeping (%d second)", rss_download_delay
                    )
                    time.sleep(rss_download_delay)

                first_element = False # Mark as not being the first element for the next iterations

                wanted_podcast_file_name = to_name_function(rss_entry)
                if wanted_podcast_file_name in downloaded_files:
                    continue

                if DOWNLOADS_LIMITS == 0:
                    continue

                if len(wanted_podcast_file_name) > file_length_limit:
                    logger.info(
                        'Your system cannot support the full podcast file name "%s". The name will be shortened',
                        wanted_podcast_file_name,
                    )

                logger.info(
                    '%s: Downloading file: "%s" saved as "%s"',
                    rss_source_name,
                    rss_entry.link,
                    to_real_podcast_file_name(rss_entry),
                )

                download_podcast(rss_source_path, rss_entry)
                DOWNLOADS_LIMITS -= 1
        else:
            logger.info("%s: Nothing new", rss_source_name)

    logger.info("Finished")
