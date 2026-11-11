import os
import sys
import re
import time
from dataclasses import dataclass
from functools import partial
from itertools import takewhile, islice
from typing import Callable, Generator, Iterator, List
import unicodedata
import feedparser
from urllib.parse import urlsplit, unquote


FILE_NAME_CHARACTER_LIMIT = 255


@dataclass
class RSSEntity:
    published_date: time.struct_time
    title: str
    type: str
    link: str


def link_to_file_name_with_extension(link: str) -> str:
    path = urlsplit(link).path
    return unquote(path).rsplit("/")[-1].replace("\\", "").lower()


def link_to_file_name(link: str) -> str:
    link = link_to_file_name_with_extension(link)
    if link.find(".") >= 0:
        link = link.rpartition(".")[0]

    return link


def link_to_extension(link: str) -> str:
    link = link_to_file_name_with_extension(link)
    if link.find(".") >= 0:
        return link.rpartition(".")[-1]

    return ""


def str_to_filename(value: str) -> str:
    value = "".join(
        part if part in ("º", "ª") else unicodedata.normalize("NFKC", part)
        for part in re.split(r"([ºª])", value)
    )
    value = re.sub(r"[\u0000-\u001F\u007F\*/:<>\"\?\\\|]", " ", value)

    return value.strip()


def file_template_to_file_name(name_template: str, entity: RSSEntity) -> str:
    publish_date_template = "%publish_date:"
    publish_date_template_len = len(publish_date_template)

    while "%publish_date:" in name_template:
        start_token = name_template.index("%publish_date:")
        token = name_template[
            start_token : name_template.index(
                "%", start_token + publish_date_template_len
            )
            + 1
        ]
        result = time.strftime(
            token[publish_date_template_len:-1].replace("$", "%"), entity.published_date
        )
        name_template = name_template.replace(token, result)

    return (
        name_template.replace("%file_name%", link_to_file_name(entity.link))
        .replace("%publish_date%", time.strftime("%Y%m%d", entity.published_date))
        .replace("%file_extension%", link_to_extension(entity.link))
        .replace("%title%", str_to_filename(entity.title))
        .strip()
    )


def _file_name_unit_length(value: str) -> int:
    """Measure a filename in the units used by the target platform."""
    if sys.platform == "win32":
        return len(value.encode("utf-16-le")) // 2
    return len(os.fsencode(value))


def limit_file_name(maximum_length: int, file_name: str) -> str:
    """Truncate a basename without splitting Unicode code points or extension."""
    if type(maximum_length) is not int or maximum_length < 1:
        raise ValueError("Filename limit must be a positive integer")

    if _file_name_unit_length(file_name) <= maximum_length:
        return file_name

    last_dot_index = file_name.rfind(".")
    if last_dot_index == -1:
        stem, extension = file_name, ""
    else:
        stem, extension = file_name[:last_dot_index], file_name[last_dot_index:]

    suffix_length = _file_name_unit_length(extension)
    if suffix_length > maximum_length:
        raise ValueError("Filename extension exceeds the configured limit")

    low, high = 0, len(stem)
    while low < high:
        middle = (low + high + 1) // 2
        if (
            _file_name_unit_length(stem[:middle]) + suffix_length
            <= maximum_length
        ):
            low = middle
        else:
            high = middle - 1
    return stem[:low] + extension

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
    to_name_function: Callable[[RSSEntity], str]
) -> Callable[[str, List[RSSEntity]], Generator[RSSEntity, None, None]]:
    return lambda from_file, raw_rss_entries: takewhile(
        lambda rss_entity: to_name_function(rss_entity) != from_file, raw_rss_entries
    )


def only_last_n_entities(
    n: int, raw_rss_entries: Iterator[RSSEntity]
) -> Iterator[RSSEntity]:
    return islice(raw_rss_entries, n)


def is_entity_newer(from_date: time.struct_time, entity: RSSEntity) -> bool:
    return entity.published_date[:3] >= from_date[:3]


def only_entities_from_date(from_date: time.struct_time) -> Callable[[RSSEntity], bool]:
    return partial(filter, partial(is_entity_newer, from_date))
