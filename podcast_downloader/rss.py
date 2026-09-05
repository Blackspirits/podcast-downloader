import io
import re
import time
import urllib.request
from dataclasses import dataclass
from functools import partial
from itertools import takewhile, islice
from typing import Callable, Dict, Generator, Iterator, List, Optional
import unicodedata
import xml.etree.ElementTree as ElementTree
import feedparser
from urllib.parse import urlsplit, unquote


FILE_NAME_CHARACTER_LIMIT = 255
FEED_TIMEOUT_SECONDS = 30


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
    value = unicodedata.normalize("NFKC", value)
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


def sanitize_xml_for_element_tree(xml_data: bytes) -> bytes:
    return re.sub(
        rb"&(?!amp;|lt;|gt;|quot;|apos;|#\d+;|#x[0-9A-Fa-f]+;)",
        b"&amp;",
        xml_data,
    )


def get_xml_namespace(xml_data: bytes, prefix: str) -> Optional[str]:
    try:
        for _, namespace in ElementTree.iterparse(
            io.BytesIO(xml_data), events=("start-ns",)
        ):
            if namespace[0] == prefix:
                return namespace[1]
    except ElementTree.ParseError:
        return None

    return None


def get_namespaced_text(
    element: ElementTree.Element, namespace: str, name: str
) -> Optional[str]:
    child = element.find("{%s}%s" % (namespace, name))
    if child is None or child.text is None:
        return None

    value = child.text.strip()
    return value or None


def get_podplay_entries(xml_data: bytes) -> List[feedparser.FeedParserDict]:
    xml_data = sanitize_xml_for_element_tree(xml_data)
    namespace = get_xml_namespace(xml_data, "pp")
    if not namespace:
        return []

    try:
        root = ElementTree.fromstring(xml_data)
    except ElementTree.ParseError:
        return []

    episode_tag = "{%s}episode" % namespace
    entries = []

    for episode in root.iter(episode_tag):
        url = get_namespaced_text(episode, namespace, "url")
        mimetype = get_namespaced_text(episode, namespace, "mimetype")
        published = get_namespaced_text(episode, namespace, "pubdate")
        if not url or not mimetype or not published:
            continue

        try:
            published_parsed = time.gmtime(int(published))
        except (ValueError, OverflowError, OSError):
            continue

        entries.append(
            feedparser.FeedParserDict(
                title=get_namespaced_text(episode, namespace, "title") or "",
                published_parsed=published_parsed,
                links=[feedparser.FeedParserDict(type=mimetype, href=url)],
            )
        )

    return entries


def add_podplay_entries(
    feed: feedparser.FeedParserDict, xml_data: bytes
) -> feedparser.FeedParserDict:
    feed_entries = feed.setdefault("entries", [])
    existing_links = {
        link.get("href")
        for entry in feed_entries
        for link in entry.get("links", [])
        if link.get("href")
    }

    for entry in get_podplay_entries(xml_data):
        url = entry["links"][0]["href"]
        if url in existing_links:
            continue

        feed_entries.append(entry)
        existing_links.add(url)

    return feed


def load_feed(
    rss_link: str, headers: Optional[Dict[str, str]] = None
) -> feedparser.FeedParserDict:
    if urlsplit(rss_link).scheme not in ("http", "https"):
        feed = feedparser.parse(rss_link)
        try:
            with open(rss_link, "rb") as source:
                return add_podplay_entries(feed, source.read())
        except (OSError, TypeError):
            return feed

    request_headers = (
        headers if headers is not None else {"User-Agent": "podcast-downloader"}
    )

    try:
        request = urllib.request.Request(rss_link, headers=request_headers)
        with urllib.request.urlopen(request, timeout=FEED_TIMEOUT_SECONDS) as response:
            xml_data = response.read()
            return add_podplay_entries(feedparser.parse(xml_data), xml_data)
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
