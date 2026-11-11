from pathlib import Path
from typing import Callable, Dict, List

from pytest_httpserver import HTTPServer

from e2e.fixures import (
    PodcastDirectory,
    PodcastDownloaderRunner,
    download_destination_directory,
    podcast_directory,
    podcast_downloader,
    use_config,
)


def build_feed(media_url: str, size: int) -> str:
    return (
        "<?xml version='1.0'?><rss version='2.0'><channel>"
        "<title>Atomic download test</title><item>"
        "<title>Episode</title>"
        "<pubDate>Fri, 04 Sep 2026 10:00:00 +0000</pubDate>"
        '<enclosure url="%s" length="%d" type="audio/mpeg"/>'
        "</item></channel></rss>"
    ) % (media_url, size)


def setup_config(use_config, podcast_directory, feed_url):
    use_config(
        {
            "if_directory_empty": "download_all_from_feed",
            "podcasts": [
                {
                    "path": podcast_directory.path(),
                    "rss_link": feed_url,
                }
            ],
        }
    )


def test_large_media_is_complete_and_leaves_no_partial_files(
    httpserver: HTTPServer,
    use_config: Callable[[Dict], None],
    podcast_downloader: Callable[[List[str]], PodcastDownloaderRunner],
    podcast_directory: PodcastDirectory,
):
    media = b"podcast audio" * 12000
    media_url = httpserver.url_for("/episode.mp3")
    feed_url = httpserver.url_for("/feed.xml")
    httpserver.expect_request("/feed.xml").respond_with_data(
        build_feed(media_url, len(media)),
        content_type="application/rss+xml",
    )
    httpserver.expect_request("/episode.mp3").respond_with_data(
        media, content_type="audio/mpeg"
    )
    setup_config(use_config, podcast_directory, feed_url)

    podcast_downloader.run()

    podcast_directory.is_containing_only(["episode.mp3"])
    destination = Path(podcast_directory.path())
    assert (destination / "episode.mp3").read_bytes() == media
    assert not list(destination.glob(".podcast-downloader-*.part"))


def test_empty_media_is_rejected_without_creating_final_file(
    httpserver: HTTPServer,
    use_config: Callable[[Dict], None],
    podcast_downloader: Callable[[List[str]], PodcastDownloaderRunner],
    podcast_directory: PodcastDirectory,
):
    media_url = httpserver.url_for("/empty.mp3")
    feed_url = httpserver.url_for("/feed.xml")
    httpserver.expect_request("/feed.xml").respond_with_data(
        build_feed(media_url, 0), content_type="application/rss+xml"
    )
    httpserver.expect_request("/empty.mp3").respond_with_data(
        b"", content_type="audio/mpeg"
    )
    setup_config(use_config, podcast_directory, feed_url)

    result = podcast_downloader.run()

    assert result.is_containing("Empty media response")
    podcast_directory.is_containing_only([])
    destination = Path(podcast_directory.path())
    assert not list(destination.glob(".podcast-downloader-*.part"))
