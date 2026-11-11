import sys
from pathlib import Path
from typing import Callable, Dict, List

import pytest
from pytest_httpserver import HTTPServer

from e2e.fixures import (
    PodcastDirectory,
    PodcastDownloaderRunner,
    download_destination_directory,
    podcast_directory,
    podcast_downloader,
    use_config,
)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX filename limits")
def test_two_episodes_remain_distinct_when_directory_path_exceeds_260_characters(
    httpserver: HTTPServer,
    use_config: Callable[[Dict], None],
    podcast_downloader: Callable[[List[str]], PodcastDownloaderRunner],
    podcast_directory: PodcastDirectory,
):
    target = Path(podcast_directory.path())
    while len(str(target)) <= 280:
        target /= "nested-podcast-folders"
        target.mkdir()

    feed_url = httpserver.url_for("/feed.xml")
    first_url = httpserver.url_for("/first-episode.mp3")
    second_url = httpserver.url_for("/second-episode.mp3")
    feed_body = (
        '<?xml version="1.0"?><rss version="2.0"><channel>'
        '<title>Long folder test</title>'
        '<item><title>First</title>'
        '<pubDate>Thu, 03 Sep 2026 10:00:00 +0000</pubDate>'
        '<enclosure url="%s" length="5" type="audio/mpeg"/>'
        '</item><item><title>Second</title>'
        '<pubDate>Fri, 04 Sep 2026 10:00:00 +0000</pubDate>'
        '<enclosure url="%s" length="6" type="audio/mpeg"/>'
        '</item></channel></rss>'
    ) % (first_url, second_url)

    httpserver.expect_request("/feed.xml").respond_with_data(
        feed_body, content_type="application/rss+xml"
    )
    httpserver.expect_request("/first-episode.mp3").respond_with_data(
        b"first", content_type="audio/mpeg"
    )
    httpserver.expect_request("/second-episode.mp3").respond_with_data(
        b"second", content_type="audio/mpeg"
    )
    use_config(
        {
            "if_directory_empty": "download_all_from_feed",
            "podcasts": [{"path": str(target), "rss_link": feed_url}],
        }
    )

    podcast_downloader.run()
    names = sorted(p.name for p in target.iterdir() if p.is_file())
    assert names == ["first-episode.mp3", "second-episode.mp3"]
    assert (target / "first-episode.mp3").read_bytes() == b"first"
    assert (target / "second-episode.mp3").read_bytes() == b"second"
    assert not (target / ".mp3").exists()
