import time
import urllib.request
import unicodedata
from dataclasses import dataclass
from functools import partial
from itertools import takewhile, islice
from typing import Callable, Generator, Iterator, List
import feedparser
from urllib.parse import urlsplit, unquote

from .filenames import fit_utf8_prefix, sanitize_file_component, utf8_size


FILE_NAME_CHARACTER_LIMIT = 255
FEED_TIMEOUT_SECONDS = 30


@dataclass
class RSSEntity:
    published_date: time.struct_time
    title: str
    type: str
    link: str
    guid: str = None


def raw_link_to_file_name_with_extension(link: str) -> str:
    path = urlsplit(link).path
    encoded_file_name = path.rsplit("/", 1)[-1]
    return unquote(encoded_file_name).lower()


def link_to_file_name_with_extension(link: str) -> str:
    return sanitize_file_component(raw_link_to_file_name_with_extension(link))


def raw_link_to_file_name(link: str) -> str:
    file_name = raw_link_to_file_name_with_extension(link)
    if "." in file_name:
        return file_name.rpartition(".")[0]
    return file_name


def link_to_file_name(link: str) -> str:
    return sanitize_file_component(raw_link_to_file_name(link))


def raw_link_to_extension(link: str) -> str:
    file_name = raw_link_to_file_name_with_extension(link)
    if "." in file_name:
        return file_name.rpartition(".")[-1]
    return ""


def link_to_extension(link: str) -> str:
    return sanitize_file_component(raw_link_to_extension(link))


def str_to_filename(value: str) -> str:
    return sanitize_file_component(value)


def _render_file_template(name_template: str, entity: RSSEntity) -> str:
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

    title = unicodedata.normalize("NFC", entity.title or "").strip()
    return (
        name_template.replace("%file_name%", raw_link_to_file_name(entity.link))
        .replace("%publish_date%", time.strftime("%Y%m%d", entity.published_date))
        .replace("%file_extension%", raw_link_to_extension(entity.link))
        .replace("%title%", title)
        .strip()
    )


def raw_file_template_to_file_name(name_template: str, entity: RSSEntity) -> str:
    return _render_file_template(name_template, entity)


def file_template_to_file_name(name_template: str, entity: RSSEntity) -> str:
    return sanitize_file_component(_render_file_template(name_template, entity))


def limit_file_name(maximum_length: int, file_name: str) -> str:
    if maximum_length <= 0:
        return ""

    file_name = sanitize_file_component(file_name)
    if utf8_size(file_name) <= maximum_length:
        return file_name

    stem, dot, extension = file_name.rpartition(".")
    if not dot:
        return fit_utf8_prefix(file_name, maximum_length)

    extension_with_dot = "." + extension
    available_for_stem = maximum_length - utf8_size(extension_with_dot)
    if available_for_stem <= 0:
        return fit_utf8_prefix(file_name, maximum_length)

    return fit_utf8_prefix(stem, available_for_stem).rstrip(" .") + extension_with_dot


def load_feed(rss_link: str) -> feedparser.FeedParserDict:
    try:
        request = urllib.request.Request(
            rss_link, headers={"User-Agent": "podcast-downloader"}
        )
        with urllib.request.urlopen(request, timeout=FEED_TIMEOUT_SECONDS) as response:
            return feedparser.parse(response)
    except Exception as error:
        return feedparser.FeedParserDict(
            feed=feedparser.FeedParserDict(),
            entries=[],
            bozo=True,
            bozo_exception=error,
        )


def get_feed_title_from_feed(feedParser: feedparser.FeedParserDict) -> str:
    return feedParser.feed.get("title", "")


def get_raw_rss_entries_from_feed(
    feedParser: feedparser.FeedParserDict,
) -> Generator[feedparser.FeedParserDict, None, None]:
    yield from feedParser.entries


def flatten_rss_links_data(
    source: Generator[feedparser.FeedParserDict, None, None]
) -> Generator[RSSEntity, None, None]:
    entities = []

    for rss_entry in source:
        published_date = rss_entry.get("published_parsed") or rss_entry.get(
            "updated_parsed"
        )
        if published_date is None:
            continue

        title = rss_entry.get("title", "")
        guid = rss_entry.get("id") or rss_entry.get("guid")
        for link in rss_entry.get("links", []):
            link_type = link.get("type")
            href = link.get("href")
            if not link_type or not href:
                continue

            entities.append(RSSEntity(published_date, title, link_type, href, guid))

    yield from sorted(entities, key=lambda entity: entity.published_date, reverse=True)


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
