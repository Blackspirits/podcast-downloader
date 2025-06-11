import re
import time
from dataclasses import dataclass
from functools import partial
from itertools import takewhile, islice
from typing import Callable, Generator, Iterable, Iterator, List # Add Iterable here
import unicodedata
import feedparser


FILE_NAME_CHARACTER_LIMIT = 255


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

    while publish_date_template in name_template:
        start_token = name_template.find(publish_date_template) # Use find instead of index for consistency with other parts
        if start_token == -1: # Should not happen with the 'in' check, but good practice
            break

        try:
            # Find the closing '%' for the custom date format
            end_format_marker_index = name_template.find("%", start_token + publish_date_template_len)
            if end_format_marker_index == -1: # Malformed template, no closing '%'
                # Log a warning (if logger is available in rss.py) or just break
                # logger.warning("Malformed date template (missing closing '%%') in '%s'", name_template[start_token:])
                break

            # Extract the raw format string, e.g., "Y-%m-%d" from "%publish_date:Y-%m-%d%"
            # It starts after publish_date_template, and ends right before the final '%'
            date_format_str = name_template[start_token + publish_date_template_len : end_format_marker_index]

            # Replace custom '$' (if used) with real '%' for strftime
            date_format_str = date_format_str.replace("$", "%")

            # Apply strftime
            result_date_str = time.strftime(date_format_str, entity.published_date)

            # Replace the full custom token, e.g., "[%publish_date:%Y-%m-%d%]"
            # The full token goes from start_token to end_format_marker_index + 1 (to include the closing '%')
            full_custom_token = name_template[start_token : end_format_marker_index + 1]
            name_template = name_template.replace(full_custom_token, result_date_str, 1) # Use count=1 to replace only the first occurrence

        except ValueError:
            # This catch is for issues within time.strftime if the format string is still bad
            # If logger is not defined in rss.py, this will cause a NameError.
            # You might need to add 'import logging' and 'logger = logging.getLogger(__name__)' to rss.py
            # or use a simple print() for debugging in development.
            # logger.warning(
            #     "Malformed date format string '%s' generated for strftime in filename template. Skipping format.",
            #     date_format_str
            # )
            break # Exit loop to prevent infinite loop on malformed token
        except Exception as e:
            # Catch any other unexpected issues during this complex replacement
            # logger.exception("An error occurred during custom date template replacement: %s", e)
            break

    # Substitui placeholders restantes, incluindo %publish_date% (fallback para a template simples)
    # Esta linha deve ser a última a lidar com datas, após todas as templates complexas.
    return (
        name_template.replace("%file_name%", link_to_file_name(entity.link))
        .replace("%publish_date%", time.strftime("%Y%m%d", entity.published_date))
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

