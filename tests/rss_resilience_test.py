import io
import time
import unittest
from unittest.mock import patch

from podcast_downloader.rss import (
    FEED_TIMEOUT_SECONDS,
    flatten_rss_links_data,
    get_feed_title_from_feed,
    load_feed,
)


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


class RssResilienceTest(unittest.TestCase):
    def test_malformed_entry_does_not_hide_following_valid_entry(self):
        valid_date = time.gmtime()
        entries = [
            {
                "title": "Missing date",
                "links": [{"type": "audio/mpeg", "href": "https://example.com/bad.mp3"}],
            },
            {
                "title": "Valid episode",
                "published_parsed": valid_date,
                "links": [{"type": "audio/mpeg", "href": "https://example.com/good.mp3"}],
            },
        ]

        result = list(flatten_rss_links_data(iter(entries)))

        self.assertEqual(1, len(result))
        self.assertEqual("Valid episode", result[0].title)
        self.assertEqual("https://example.com/good.mp3", result[0].link)

    def test_updated_date_is_used_when_published_date_is_missing(self):
        updated_date = time.gmtime()
        entries = [
            {
                "updated_parsed": updated_date,
                "links": [{"type": "audio/mpeg", "href": "https://example.com/ep.mp3"}],
            }
        ]

        result = list(flatten_rss_links_data(iter(entries)))

        self.assertEqual(1, len(result))
        self.assertEqual(updated_date, result[0].published_date)
        self.assertEqual("", result[0].title)

    def test_links_without_type_or_href_are_skipped(self):
        entries = [
            {
                "published_parsed": time.gmtime(),
                "links": [
                    {"href": "https://example.com/no-type.mp3"},
                    {"type": "audio/mpeg"},
                ],
            }
        ]

        self.assertEqual([], list(flatten_rss_links_data(iter(entries))))

    def test_missing_feed_title_returns_empty_string(self):
        feed = {"feed": {}}

        class Feed(dict):
            @property
            def feed(self):
                return self["feed"]

        self.assertEqual("", get_feed_title_from_feed(Feed(feed)))

    def test_feed_download_uses_timeout(self):
        xml = b"""<?xml version='1.0'?><rss version='2.0'><channel><title>Test</title></channel></rss>"""

        with patch(
            "podcast_downloader.rss.urllib.request.urlopen",
            return_value=Response(xml),
        ) as urlopen:
            feed = load_feed("https://example.com/feed.xml")

        self.assertEqual("Test", feed.feed.title)
        self.assertEqual(FEED_TIMEOUT_SECONDS, urlopen.call_args.kwargs["timeout"])

    def test_feed_network_error_becomes_bozo_feed(self):
        with patch(
            "podcast_downloader.rss.urllib.request.urlopen",
            side_effect=TimeoutError("timeout"),
        ):
            feed = load_feed("https://example.com/feed.xml")

        self.assertTrue(feed.bozo)
        self.assertEqual([], feed.entries)
        self.assertIsInstance(feed.bozo_exception, TimeoutError)


if __name__ == "__main__":
    unittest.main()
