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


def test_downloads_standard_and_podplay_episode_entries(
    httpserver: HTTPServer,
    use_config: Callable[[Dict], None],
    podcast_downloader: Callable[[List[str]], PodcastDownloaderRunner],
    podcast_directory: PodcastDirectory,
):
    standard_file = "standard.mp3"
    first_custom_file = "custom-one.mp3"
    second_custom_file = "custom-two.mp3"
    standard_url = httpserver.url_for("/" + standard_file)
    first_custom_url = httpserver.url_for("/" + first_custom_file)
    second_custom_url = httpserver.url_for("/" + second_custom_file)

    feed_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:pp="https://example.com/podplay">
  <channel>
    <title>Podplay podcast</title>
    <item>
      <title>Standard episode</title>
      <pubDate>Fri, 04 Sep 2026 10:00:00 +0000</pubDate>
      <enclosure url="{standard_url}" length="8" type="audio/mpeg"/>
    </item>
    <pp:episode>
      <pp:url>{first_custom_url}</pp:url>
      <pp:mimetype>audio/mpeg</pp:mimetype>
      <pp:pubdate>1788429600</pp:pubdate>
      <pp:title>First custom episode</pp:title>
    </pp:episode>
    <pp:episode>
      <pp:url>{second_custom_url}</pp:url>
      <pp:mimetype>audio/mpeg</pp:mimetype>
      <pp:pubdate>1788343200</pp:pubdate>
      <pp:title>Second custom episode</pp:title>
    </pp:episode>
  </channel>
</rss>
"""

    httpserver.expect_request("/feed.xml").respond_with_data(
        feed_xml, content_type="application/rss+xml"
    )
    httpserver.expect_request("/" + standard_file).respond_with_data("standard")
    httpserver.expect_request("/" + first_custom_file).respond_with_data("custom one")
    httpserver.expect_request("/" + second_custom_file).respond_with_data("custom two")

    use_config(
        {
            "if_directory_empty": "download_all_from_feed",
            "podcasts": [
                {
                    "path": podcast_directory.path(),
                    "rss_link": httpserver.url_for("/feed.xml"),
                }
            ],
        }
    )

    podcast_downloader.run()

    podcast_directory.is_containing_only(
        [standard_file, first_custom_file, second_custom_file]
    )
