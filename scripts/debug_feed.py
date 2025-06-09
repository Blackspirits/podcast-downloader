# scripts/debug_feed.py (Improved Version)

import argparse
from functools import partial
from pathlib import Path
import sys

# Ensure the script can find the podcast_downloader module
# This adjusts the path to look in the parent directory
sys.path.append(str(Path(__file__).resolve().parents[1]))

from podcast_downloader.__main__ import get_system_file_name_limit
from podcast_downloader.downloaded import get_downloaded_files, get_extensions_checker
from podcast_downloader.parameters import load_configuration_file
from podcast_downloader.rss import (
    build_only_allowed_filter_for_link_data,
    build_only_new_entities,
    file_template_to_file_name,
    flatten_rss_links_data,
    get_raw_rss_entries_from_feed,
    limit_file_name,
    load_feed,
)
from podcast_downloader.utils import compose

def main():
    """Main function to run the debug script."""
    parser = argparse.ArgumentParser(description="Debug a podcast feed based on the downloader's configuration.")
    parser.add_argument(
        "--config",
        type=str,
        default="~/.podcast_downloader_config.json",
        help="Path to the configuration file (defaults to ~/.podcast_downloader_config.json)"
    )
    parser.add_argument(
        "--podcast-index",
        type=int,
        default=0,
        help="The index of the podcast in the config's 'podcasts' list to debug (defaults to 0)"
    )
    args = parser.parse_args()

    # --- Configuration Loading ---
    config_path = Path(args.config).expanduser()
    if not config_path.is_file():
        print(f"Error: Configuration file not found at '{config_path}'")
        sys.exit(1)

    try:
        config = load_configuration_file(config_path)
        if not config.get("podcasts"):
            print("Error: No 'podcasts' list found in the configuration file.")
            sys.exit(1)
        podcast_config = config["podcasts"][args.podcast_index]
    except IndexError:
        print(f"Error: Invalid podcast index. There is no podcast at index {args.podcast_index}.")
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred while loading the configuration: {e}")
        sys.exit(1)

    podcast_name = podcast_config.get("name", "Unnamed Podcast")
    print(f"--- Debugging Podcast: {podcast_name} ---")

    # --- Core Logic (Modernized) ---
    rss_source_link = podcast_config["rss_link"]
    feed = load_feed(rss_source_link)

    rss_podcast_extensions = podcast_config.get("podcast_extensions", {".mp3": "audio/mpeg"})
    rss_podcast_file_name_template = podcast_config.get("file_name_template", "%file_name%.%file_extension%")
    rss_source_path = Path(podcast_config["path"]).expanduser()

    allow_link_types = list(set(rss_podcast_extensions.values()))

    all_feed_entries = compose(
        list,
        partial(filter, build_only_allowed_filter_for_link_data(allow_link_types)),
        flatten_rss_links_data,
        get_raw_rss_entries_from_feed,
    )(feed)

    downloaded_files_set = set(get_downloaded_files(
        get_extensions_checker(rss_podcast_extensions.keys()), rss_source_path
    ))

    to_name_function = partial(file_template_to_file_name, rss_podcast_file_name_template)
    file_length_limit = get_system_file_name_limit(podcast_config)
    to_real_podcast_file_name = compose(
        partial(limit_file_name, file_length_limit), to_name_function
    )

    all_feed_files = [to_real_podcast_file_name(entry) for entry in all_feed_entries][::-1]

    # Find the last downloaded file more safely
    last_downloaded_file = None
    if downloaded_files_set:
        downloaded_in_feed_order = [f for f in all_feed_files if f in downloaded_files_set]
        if downloaded_in_feed_order:
            last_downloaded_file = downloaded_in_feed_order[-1]

    print(f"Last downloaded file found: {last_downloaded_file}")

    # Determine missing files
    if last_downloaded_file:
        download_limiter_function = build_only_new_entities(to_name_function, last_downloaded_file)
        missing_files = list(download_limiter_function(all_feed_entries))
    else:
        # If no files are downloaded, consider all feed entries as missing
        missing_files = all_feed_entries
        
    missing_files_set = {to_real_podcast_file_name(entry) for entry in missing_files}

    print("\n--- Feed Analysis ---")
    print(f"{'Status':<12} | {'Episode Title':<70} | {'Generated Filename'}")
    print(f"{'-'*12}-+-{'-'*70}-+-{'-'*50}")

    for entry in all_feed_entries:
        feed_file = to_real_podcast_file_name(entry)
        
        # Determine status using efficient set lookups
        if feed_file in missing_files_set:
            status = "to-download"
        elif feed_file in downloaded_files_set:
            status = "downloaded"
        else:
            status = "ignored"

        # Truncate title for cleaner printing
        title = (entry.title[:67] + '...') if len(entry.title) > 70 else entry.title
        print(f"{status:<12} | {title:<70} | {feed_file}")


if __name__ == "__main__":
    main()
