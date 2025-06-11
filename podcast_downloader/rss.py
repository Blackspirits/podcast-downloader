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

    while publish_date_template in name_template: # Use 'in' para mais robustez
        start_token = name_template.index(publish_date_template)
        try:
            end_token_index = name_template.index("%", start_token + publish_date_template_len)
            token = name_template[start_token : end_token_index + 1]
            date_format_str = token[publish_date_template_len:-1].replace("$", "%")
            result_date_str = time.strftime(date_format_str, entity.published_date)
            name_template = name_template.replace(token, result_date_str)
        except ValueError:
            # Caso o '%' final esteja em falta ou haja outro erro de formatação
            logger.warning(
                "Malformed date template found in filename template: '%s'. Skipping format.",
                name_template[start_token:start_token+50] # log part of the template
            )
            name_template = name_template.replace(token, "") # Remove the malformed token or replace with empty string
            break # Exit loop to prevent infinite loop on malformed token

    # Substitui placeholders restantes, incluindo %publish_date% se não foi substituído antes (o que é raro)
    return (
        name_template.replace("%file_name%", link_to_file_name(entity.link))
        .replace("%publish_date%", time.strftime("%Y%m%d", entity.published_date)) # Manter como fallback se a template de cima não for usada.
                                                                                # Se usar apenas %publish_date% no config, este é ativado.
                                                                                # Se usar a template mais completa, este já não fará nada.
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

