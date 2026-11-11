import logging
import os
import sys
import re
import time
import urllib.request
from dataclasses import dataclass
from functools import partial
from itertools import takewhile, islice
from typing import Callable, Dict, Generator, Iterator, List, Optional
import unicodedata
import feedparser
from urllib.parse import urljoin, urlsplit, unquote


FILE_NAME_CHARACTER_LIMIT = 255
FEED_TIMEOUT_SECONDS = 30
DEFAULT_MAX_RSS_PAGES = 1000


class RSSPaginationError(RuntimeError):
    """An RSS pagination run could not be completed safely."""


class RSSPaginationLimitExceeded(RSSPaginationError):
    """The configured RSS page limit was reached before pagination ended."""


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

def get_next_feed_link(feed: feedparser.FeedParserDict) -> Optional[str]:
    for link in feed.get("feed", {}).get("links", []):
        if str(link.get("rel", "")).lower() == "next" and link.get("href"):
            return link["href"]

    return None


def _http_origin(url: str):
    """Normalize the scheme, hostname and port for HTTP(S) origin checks."""
    try:
        parts = urlsplit(url)
        if (
            parts.scheme.lower() not in ("http", "https")
            or not parts.hostname
            or parts.username is not None
            or parts.password is not None
        ):
            return None
        port = parts.port or (443 if parts.scheme.lower() == "https" else 80)
        if not 1 <= port <= 65535:
            return None
    except ValueError:
        return None
    return parts.scheme.lower(), parts.hostname.lower().rstrip("."), port


class _SameOriginRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, allowed_origin):
        self.allowed_origin = allowed_origin

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if _http_origin(newurl) != self.allowed_origin:
            raise RSSPaginationError(
                "Blocked RSS feed redirect to a different origin"
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _open_feed_request(request, timeout, allowed_origin):
    opener = urllib.request.build_opener(_SameOriginRedirectHandler(allowed_origin))
    return opener.open(request, timeout=timeout)


def _fetch_paginated_feed(rss_link, allowed_origin, headers):
    if _http_origin(rss_link) != allowed_origin:
        raise RSSPaginationError(
            "Blocked RSS pagination link outside the initial feed origin"
        )
    page = _load_single_feed(rss_link, headers, allowed_origin=allowed_origin)
    if page.get("bozo", False) and not page.entries:
        raise RSSPaginationError(
            "Could not load an RSS pagination page: %s"
            % page.get("bozo_exception", "invalid feed")
        )
    return page


def _load_single_feed(
    rss_link: str,
    headers: Optional[Dict[str, str]] = None,
    allowed_origin=None,
) -> feedparser.FeedParserDict:
    if urlsplit(rss_link).scheme not in ("http", "https"):
        return feedparser.parse(rss_link)

    request_headers = headers if headers is not None else {"User-Agent": "podcast-downloader"}
    origin = allowed_origin or _http_origin(rss_link)

    try:
        if origin is None or _http_origin(rss_link) != origin:
            raise RSSPaginationError("RSS feed URL does not match the allowed origin")
        request = urllib.request.Request(rss_link, headers=request_headers)
        with _open_feed_request(request, FEED_TIMEOUT_SECONDS, origin) as response:
            final_url = response.geturl() if hasattr(response, "geturl") else rss_link
            if final_url and _http_origin(final_url) != origin:
                raise RSSPaginationError(
                    "Blocked RSS feed response from a different origin"
                )
            response_headers = {
                key.lower(): value
                for key, value in getattr(response, "headers", {}).items()
            }
            response_headers.setdefault("content-location", final_url or rss_link)
            return feedparser.parse(response, response_headers=response_headers)
    except Exception as error:
        return feedparser.FeedParserDict(
            feed=feedparser.FeedParserDict(),
            entries=[],
            bozo=True,
            bozo_exception=error,
        )


def load_feed(
    rss_link: str,
    headers: Optional[Dict[str, str]] = None,
    max_pages: int = DEFAULT_MAX_RSS_PAGES,
) -> feedparser.FeedParserDict:
    if type(max_pages) is not int or max_pages < 1:
        raise ValueError("max_rss_pages must be a positive integer")

    feed = _load_single_feed(rss_link, headers)
    if feed.get("bozo", False) and not feed.entries:
        return feed

    current_feed = feed
    current_link = rss_link
    visited_links = {rss_link}
    allowed_origin = _http_origin(rss_link)

    while True:
        next_link = get_next_feed_link(current_feed)
        if not next_link:
            break

        base_link = (
            current_feed.get("href")
            or current_feed.get("headers", {}).get("content-location")
            or current_link
        )
        next_link = urljoin(base_link, next_link)
        if allowed_origin is None or _http_origin(next_link) != allowed_origin:
            raise RSSPaginationError(
                "Blocked RSS pagination link outside the initial feed origin"
            )
        if next_link in visited_links:
            break
        if len(visited_links) >= max_pages:
            raise RSSPaginationLimitExceeded(
                "RSS pagination for %s exceeded max_rss_pages=%d; "
                "increase the limit to load the complete feed" % (rss_link, max_pages)
            )

        visited_links.add(next_link)
        next_feed = _fetch_paginated_feed(next_link, allowed_origin, headers)
        if next_feed.get("bozo", False) and not next_feed.entries:
            raise RSSPaginationError(
                "Could not load RSS pagination page %s: %s"
                % (next_link, next_feed.get("bozo_exception", "invalid feed"))
            )

        feed.entries.extend(next_feed.entries)
        current_feed = next_feed
        current_link = next_link

    return feed

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
        for link in rss_entry.get("links", []):
            link_type = link.get("type")
            href = link.get("href")
            if not link_type or not href:
                continue

            entities.append(RSSEntity(published_date, title, link_type, href))

    is_ascending = all(
        first.published_date <= second.published_date
        for first, second in zip(entities, entities[1:])
    )
    if (
        len(entities) > 1
        and is_ascending
        and entities[0].published_date < entities[-1].published_date
    ):
        entities.reverse()

    yield from entities


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
