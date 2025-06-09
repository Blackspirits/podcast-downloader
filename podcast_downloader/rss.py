import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from itertools import islice, takewhile
from pathlib import Path
from typing import Callable, Generator, Iterable, List
from urllib.parse import urlparse

import feedparser

# --- Data Structures ---

@dataclass(frozen=True)
class RSSEntity:
    """Represents a single downloadable entity (e.g., an episode) from an RSS feed."""
    published_date: datetime
    title: str
    type: str
    link: str

# --- Parsing and Sanitization ---

def _parse_url_path(link: str) -> Path:
    """Safely parses a URL and returns the path component as a Path object."""
    # Remove query string before parsing to isolate the filename
    if "?" in link:
        link = link.rpartition("?")[0]
    
    # Use standard libraries to correctly parse the URL
    parsed_url = urlparse(link)
    return Path(parsed_url.path)


def link_to_file_name_with_extension(link: str) -> str:
    """Extracts the filename with its extension from a URL."""
    return _parse_url_path(link).name.lower()


def link_to_file_name(link: str) -> str:
    """Extracts the filename without its extension from a URL."""
    return _parse_url_path(link).stem.lower()


def link_to_extension(link: str) -> str:
    """Extracts the file extension from a URL."""
    # .lstrip('.') handles cases like ".mp3" -> "mp3"
    return _parse_url_path(link).suffix.lower().lstrip('.')


def sanitize_for_filename(value: str) -> str:
    """
    Normalizes and sanitizes a string to be safely used as part of a filename.
    Removes control characters and characters forbidden in Windows filenames.
    """
    # NFKC normalization handles many special characters and compatibility issues.
    value = unicodedata.normalize("NFKC", value)
    # Remove control characters and reserved filename characters.
    value = re.sub(r"[\u0000-\u001F\u007F/\\:<>*\"?|]", " ", value)
    return value.strip()


def file_template_to_file_name(name_template: str, entity: RSSEntity) -> str:
    """
    Gera um nome de ficheiro a partir de um template e de uma entidade RSS.

    Suporta os seguintes placeholders:
    - %title%: Título do episódio (sanitizado).
    - %file_name%: Nome original do ficheiro sem extensão.
    - %file_extension%: Extensão do ficheiro (ex: mp3).
    - %publish_date%: Data de publicação no formato AAAAMMDD.
    - [%publish_date:FORMATO%]: Data de publicação com formatação customizada.
    """

    # 1. Substituir [%publish_date:FORMATO%] usando regex
    def date_format_matcher(match: re.Match) -> str:
        format_str = match.group(1)
        try:
            return entity.published_date.strftime(format_str)
        except Exception:
            return "invalid_date"

    name_template = re.sub(r"\[%publish_date:([^%\]]+)%\]", date_format_matcher, name_template)

    # 2. Substituições padrão
    replacements = {
        "%title%": sanitize_for_filename(entity.title),
        "%file_name%": link_to_file_name(entity.link),
        "%file_extension%": link_to_extension(entity.link),
        "%publish_date%": entity.published_date.strftime("%Y%m%d"),
    }

    for token, value in replacements.items():
        name_template = name_template.replace(token, value)

    return name_template.strip()


def limit_file_name(maximum_length: int, file_name: str) -> str:
    """
    Truncates a filename to a maximum length while preserving the extension.
    """
    if len(file_name) <= maximum_length:
        return file_name

    name_part, _, extension = file_name.rpartition(".")
    
    if not extension or len(extension) > maximum_length:
        # If there's no extension or the extension itself is too long, just truncate the whole thing.
        return file_name[:maximum_length]

    # Calculate how much space is left for the name part.
    # The +1 accounts for the dot separator.
    available_length_for_name = maximum_length - len(extension) - 1
    
    if available_length_for_name < 0:
        # Not even enough space for the extension, return truncated extension.
        return file_name[-maximum_length:]

    return f"{name_part[:available_length_for_name]}.{extension}"


# --- Feed Processing ---

def load_feed(rss_link: str) -> feedparser.FeedParserDict:
    """Loads and parses an RSS feed from a URL."""
    return feedparser.parse(rss_link)


def get_feed_title_from_feed(feed: feedparser.FeedParserDict) -> str:
    """Extracts the main title from a parsed feed."""
    return feed.feed.title


def get_raw_rss_entries_from_feed(feed: feedparser.FeedParserDict) -> Generator[feedparser.FeedParserDict, None, None]:
    """Yields all entries from a parsed feed."""
    yield from feed.entries


def flatten_rss_links_data(
    source: Iterable[feedparser.FeedParserDict],
) -> Generator[RSSEntity, None, None]:
    """
    Converts raw feed entries into a flat stream of RSSEntity objects.
    An entry with multiple links (e.g., mp3, ogg) will yield multiple entities.
    """
    for rss_entry in source:
        if not hasattr(rss_entry, "published_parsed") or not rss_entry.published_parsed:
            continue  # Skip entries with no valid date

        # Convert feedparser's time.struct_time to a modern datetime object
        published_datetime = datetime.fromtimestamp(time.mktime(rss_entry.published_parsed))
        
        for link in getattr(rss_entry, "links", []):
            href = link.get("href")
            if href:
                yield RSSEntity(
                    published_date=published_datetime,
                    title=rss_entry.get("title", "Untitled"),
                    type=link.get("type"),
                    link=href,
                )

# --- Filtering and Selection Logic ---

def build_only_allowed_filter_for_link_data(
    allowed_types: List[str],
) -> Callable[[RSSEntity], bool]:
    """Returns a function that filters for entities with an allowed MIME type."""
    return lambda entity: entity.type in allowed_types


def build_only_new_entities(
    to_name_function: Callable[[RSSEntity], str],
    from_file: str,
) -> Callable[[Iterable[RSSEntity]], Iterable[RSSEntity]]:
    """
    Returns a function that takes entities from an iterable until it encounters
    the one corresponding to `from_file`.
    """
    return partial(takewhile, lambda entity: to_name_function(entity) != from_file)


def only_last_n_entities(n: int, entities: Iterable[RSSEntity]) -> Iterable[RSSEntity]:
    """Returns an iterator for the first `n` entities from an iterable."""
    return islice(entities, n)


def is_entity_newer(from_date: datetime, entity: RSSEntity) -> bool:
    """Checks if an entity's publication date is on or after `from_date`."""
    # Compare only the date part to ignore time differences within the same day.
    return entity.published_date.date() >= from_date.date()


def only_entities_from_date(from_date: datetime) -> Callable[[RSSEntity], bool]:
    """Returns a filter function that checks if an entity is newer than a given date."""
    return partial(is_entity_newer, from_date)
