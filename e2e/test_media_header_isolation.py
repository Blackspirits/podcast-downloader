from typing import Callable, Dict, List
from urllib.parse import urlsplit, urlunsplit

from pytest_httpserver import HTTPServer

from e2e.fixures import (
    PodcastDirectory,
    PodcastDownloaderRunner,
    download_destination_directory,
    podcast_directory,
    podcast_downloader,
    use_config,
)


SECRET = "Bearer example-private-token"
CUSTOM_SECRET = "private-custom-header"


def other_host_url(url: str) -> str:
    parts = urlsplit(url)
    other_host = "127.0.0.1" if parts.hostname == "localhost" else "localhost"
    return urlunsplit(
        (parts.scheme, "%s:%d" % (other_host, parts.port), parts.path,
         parts.query, parts.fragment)
    )


def configure_feed(
    use_config,
    podcast_directory,
    rss_link: str,
):
    use_config(
        {
            "if_directory_empty": "download_all_from_feed",
            "http_headers": {
                "Authorization": SECRET,
                "X-Custom-Secret": CUSTOM_SECRET,
            },
            "podcasts": [
                {
                    "rss_link": rss_link,
                    "path": podcast_directory.path(),
                }
            ],
        }
    )


def rss_with_enclosure(url):
    return (
        "<?xml version='1.0'?><rss version='2.0'><channel>"
        "<title>Media header test</title><item><title>Episode</title>"
        "<pubDate>Fri, 04 Sep 2026 10:00:00 +0000</pubDate>"
        '<enclosure url="%s" length="11" type="audio/mpeg"/>' % url
        + "</item></channel></rss>"
    )


def logged_requests(httpserver, path):
    return [request for request, _ in httpserver.log if request.path == path]


def test_same_origin_media_keeps_feed_auth_headers(
    httpserver: HTTPServer,
    use_config: Callable[[Dict], None],
    podcast_downloader: Callable[[List[str]], PodcastDownloaderRunner],
    podcast_directory: PodcastDirectory,
):
    media_url = httpserver.url_for("/same.mp3")
    rss_url = httpserver.url_for("/rss.xml")
    httpserver.expect_request("/rss.xml").respond_with_data(
        rss_with_enclosure(media_url), content_type="application/rss+xml"
    )
    httpserver.expect_request("/same.mp3").respond_with_data("audio bytes")
    configure_feed(use_config, podcast_directory, rss_url)

    podcast_downloader.run()
    podcast_directory.is_containing_only(["same.mp3"])
    request = logged_requests(httpserver, "/same.mp3")[0]
    assert request.headers.get("Authorization") == SECRET
    assert request.headers.get("X-Custom-Secret") == CUSTOM_SECRET


def test_external_media_cdn_never_receives_feed_auth_headers(
    httpserver: HTTPServer,
    use_config: Callable[[Dict], None],
    podcast_downloader: Callable[[List[str]], PodcastDownloaderRunner],
    podcast_directory: PodcastDirectory,
):
    media_url = other_host_url(httpserver.url_for("/external.mp3"))
    rss_url = httpserver.url_for("/rss.xml")
    httpserver.expect_request("/rss.xml").respond_with_data(
        rss_with_enclosure(media_url), content_type="application/rss+xml"
    )
    httpserver.expect_request("/external.mp3").respond_with_data("audio bytes")
    configure_feed(use_config, podcast_directory, rss_url)

    podcast_downloader.run()
    podcast_directory.is_containing_only(["external.mp3"])
    request = logged_requests(httpserver, "/external.mp3")[0]
    assert request.headers.get("Authorization") is None
    assert request.headers.get("X-Custom-Secret") is None


def test_media_redirect_to_external_cdn_strips_feed_auth_headers(
    httpserver: HTTPServer,
    use_config: Callable[[Dict], None],
    podcast_downloader: Callable[[List[str]], PodcastDownloaderRunner],
    podcast_directory: PodcastDirectory,
):
    rss_url = httpserver.url_for("/rss.xml")
    initial_media_url = httpserver.url_for("/redirect.mp3")
    final_media_url = other_host_url(httpserver.url_for("/final.mp3"))

    httpserver.expect_request("/rss.xml").respond_with_data(
        rss_with_enclosure(initial_media_url), content_type="application/rss+xml"
    )
    httpserver.expect_request("/redirect.mp3").respond_with_data(
        "redirect", status=302, headers={"Location": final_media_url}
    )
    httpserver.expect_request("/final.mp3").respond_with_data("audio bytes")
    configure_feed(use_config, podcast_directory, rss_url)

    podcast_downloader.run()
    podcast_directory.is_containing_only(["redirect.mp3"])

    first = logged_requests(httpserver, "/redirect.mp3")[0]
    last = logged_requests(httpserver, "/final.mp3")[0]
    assert first.headers.get("Authorization") == SECRET
    assert last.headers.get("Authorization") is None
    assert last.headers.get("X-Custom-Secret") is None
