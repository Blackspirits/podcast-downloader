import re
import time
import logging
from dataclasses import dataclass
from functools import partial
from itertools import takewhile, islice
from typing import Callable, Generator, Iterable, Iterator, List # Add Iterable here
import unicodedata
import feedparser


FILE_NAME_CHARACTER_LIMIT = 255

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

@dataclass
class RSSEntity:
    published_date: time.struct_time
    title: str
    type: str
    link: str


def link_to_file_name_with_extension(link: str) -> str:
    if link.find("?") > 0:
        link = link.rpartition("?")[0]

    return link.rpartition("/")[-1].lower()


def link_to_file_name(link: str) -> str:
    link = link_to_file_name_with_extension(link)
    if link.find(".") > 0:
        link = link.rpartition(".")[0]

    return link


def link_to_extension(link: str) -> str:
    link = link_to_file_name_with_extension(link)
    if link.find(".") > 0:
        return link.rpartition(".")[-1]

    return ""


def str_to_filename(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    value = re.sub(r"[\u0000-\u001F\u007F\*/:<>\"\?\\\|]", " ", value)

    return value.strip()


def file_template_to_file_name(name_template: str, entity: RSSEntity) -> str:
    publish_date_template = "%publish_date:"
    publish_date_template_len = len(publish_date_template)

    # Process custom date formats like %publish_date:%Y-%m-%d%
    temp_name_template = name_template # Work on a temporary copy
    while publish_date_template in temp_name_template:
        start_token_idx = temp_name_template.find(publish_date_template)
        if start_token_idx == -1: # Should not happen, but a safeguard
            break

        try:
            # The format string starts immediately after publish_date_template
            format_start_idx = start_token_idx + publish_date_template_len
            # Find the closing '%' for the custom date format
            end_token_idx = temp_name_template.find("%", format_start_idx)

            if end_token_idx == -1: # Malformed template, no closing '%'
                logger.warning(
                    "Malformed date template found (missing closing '%%') in filename template: '%s'. Skipping format.",
                    temp_name_template[start_token_idx:start_token_idx+50]
                )
                # Replace the malformed part to avoid infinite loop or literal appearance
                temp_name_template = temp_name_template.replace(temp_name_template[start_token_idx:], "", 1)
                continue # Try to find other templates
            
            # Extract the format string, e.g., "%Y-%m-%d"
            date_format_str = temp_name_template[format_start_idx : end_token_idx]
            date_format_str = date_format_str.replace("$", "%") # Handle potential '$' to '%' conversion

            result_date_str = time.strftime(date_format_str, entity.published_date)

            # Replace the entire custom token, e.g., "[%publish_date:%Y-%m-%d%]"
            full_custom_token = temp_name_template[start_token_idx : end_token_idx + 1]
            temp_name_template = temp_name_template.replace(full_custom_token, result_date_str, 1)

        except ValueError as e: # This handles cases where time.strftime gets an invalid format
            logger.warning(
                "Invalid strftime format '%s' from template '%s'. Error: %s. Replacing with empty string.",
                date_format_str,
                temp_name_template[start_token_idx : end_token_idx + 1],
                e
            )
            # Replace the malformed token with an empty string or a generic date
            temp_name_template = temp_name_template.replace(temp_name_template[start_token_idx : end_token_idx + 1], "", 1)
            continue # Try to find other templates
        except Exception as e:
            logger.exception(
                "An unexpected error occurred during custom date template replacement for '%s'.",
                temp_name_template[start_token_idx:start_token_idx+50]
            )
            temp_name_template = temp_name_template.replace(temp_name_template[start_token_idx : end_token_idx + 1], "", 1)
            continue


    # Replace standard placeholders AFTER custom date formats are handled
    return (
        temp_name_template.replace("%file_name%", link_to_file_name(entity.link))
        .replace("%publish_date%", time.strftime("%Y%m%d", entity.published_date)) # Fallback for plain %publish_date%
        .replace("%file_extension%", link_to_extension(entity.link))
        .replace("%title%", str_to_filename(entity.title))
        .strip()
    )


def limit_file_name(maximum_length: int, file_name: str) -> str:
    last_dot_index = file_name.rfind(".")
    if last_dot_index == -1:
        return file_name[:maximum_length]

    file_name_length = len(file_name)
    if file_name_length <= maximum_length:
        return file_name

    return (
        file_name[: maximum_length - file_name_length + last_dot_index]
        + file_name[last_dot_index:]
    )


def load_feed(rss_link: str) -> feedparser.FeedParserDict:
    return feedparser.parse(rss_link)


def get_feed_title_from_feed(feedParser: feedparser.FeedParserDict) -> str:
    return feedParser.feed.title


def get_raw_rss_entries_from_feed(
    feedParser: feedparser.FeedParserDict,
) -> Generator[feedparser.FeedParserDict, None, None]:
    yield from feedParser.entries


def flatten_rss_links_data(
    source: Generator[feedparser.FeedParserDict, None, None]
) -> Generator[RSSEntity, None, None]:
    return (
        RSSEntity(
            rss_entry.published_parsed,
            rss_entry.title,
            link.type,
            link.get("href", None),
        )
        for rss_entry in source
        for link in rss_entry.links
    )


def build_only_allowed_filter_for_link_data(
    allowed_types: List[str],
) -> Callable[[RSSEntity], bool]:
    return lambda link_data: link_data.type in allowed_types

def build_only_new_entities(
    to_name_function: Callable[[RSSEntity], str],
    from_file: str,
    raw_rss_entries: Iterable[RSSEntity]
) -> Generator[RSSEntity, None, None]:
    """
    Returns a generator that yields RSS entities newer than (or not matching) the given from_file.
    """
    return takewhile(
        lambda rss_entity: to_name_function(rss_entity) != from_file, raw_rss_entries
    )

def only_last_n_entities(
    n: int, raw_rss_entries: Iterator[RSSEntity]
) -> Iterator[RSSEntity]:
    return islice(raw_rss_entries, n)


def is_entity_newer(from_date: time.struct_time, entity: RSSEntity) -> bool:
    return entity.published_date[:3] >= from_date[:3]


def only_entities_from_date(from_date: time.struct_time, raw_rss_entries: Iterator[RSSEntity]) -> Iterator[RSSEntity]:
    return filter(lambda entity: is_entity_newer(from_date, entity), raw_rss_entries)

