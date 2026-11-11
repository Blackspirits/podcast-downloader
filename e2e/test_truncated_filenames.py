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


def test_truncated_episode_name_is_not_downloaded_on_every_run(
    httpserver: HTTPServer,
    use_config: Callable[[Dict], None],
    podcast_downloader: Callable[[List[str]], PodcastDownloaderRunner],
    podcast_directory: PodcastDirectory,
):
    original_name = ("a" * 300) + ".mp3"
    media_path = "/" + original_name
    media_url = httpserver.url_for(media_path)
    rss_url = httpserver.url_for("/feed.xml")
    body = (
        "<?xml version='1.0'?><rss version='2.0'><channel>"
        "<title>Long filename regression</title><item><title>Episode</title>"
        "<pubDate>Fri, 04 Sep 2026 10:00:00 +0000</pubDate>"
        '<enclosure url="%s" length="11" type="audio/mpeg"/>'
        "</item></channel></rss>"
    ) % media_url

    httpserver.expect_request("/feed.xml").respond_with_data(
        body, content_type="application/rss+xml"
    )
    httpserver.expect_request(media_path).respond_with_data(
        "audio bytes", content_type="audio/mpeg"
    )
    use_config(
        {
            "if_directory_empty": "download_all_from_feed",
            "podcasts": [
                {
                    "path": podcast_directory.path(),
                    "rss_link": rss_url,
                }
            ],
        }
    )

    podcast_downloader.run()
    folder = Path(podcast_directory.path())
    files_before = sorted(p.name for p in folder.iterdir() if p.is_file())
    assert len(files_before) == 1
    assert files_before[0].endswith(".mp3")
    assert files_before[0] != original_name

    podcast_downloader.run()
    files_after = sorted(p.name for p in folder.iterdir() if p.is_file())
    assert files_after == files_before
    media_requests = [
        req for req, _ in httpserver.log if req.path == media_path
    ]
    assert len(media_requests) == 1
