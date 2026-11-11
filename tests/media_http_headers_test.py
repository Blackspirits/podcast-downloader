import unittest
import urllib.request

from podcast_downloader.__main__ import (
    _MediaRedirectHandler,
    _http_origin,
    _media_request_headers,
)


class MediaHttpHeadersTest(unittest.TestCase):
    def setUp(self):
        self.headers = {
            "Authorization": "Bearer private-feed-token",
            "Cookie": "session=private",
            "X-Custom-Secret": "private",
        }

    def test_credentials_are_kept_for_same_origin_media(self):
        result = _media_request_headers(
            "https://example.com/feed.xml",
            "https://EXAMPLE.com:443/episode.mp3",
            self.headers,
        )
        self.assertEqual(self.headers, result)

    def test_credentials_not_forwarded_to_external_cdn(self):
        for media_url in (
            "https://cdn.example.com/episode.mp3",
            "http://example.com/episode.mp3",
            "https://example.com:8443/episode.mp3",
            "https://example.com@evil.example/episode.mp3",
        ):
            with self.subTest(media_url=media_url):
                result = _media_request_headers(
                    "https://example.com/feed.xml", media_url, self.headers
                )
                self.assertEqual({"User-Agent": "podcast-downloader"}, result)

    def test_reject_unsafe_media_urls_before_request(self):
        for media_url in (
            "file:///etc/passwd",
            "ftp://example.com/episode.mp3",
            "https://example.com:bad/file.mp3",
            "https://username:password@example.com/file.mp3",
        ):
            with self.subTest(media_url=media_url):
                with self.assertRaises(ValueError):
                    _media_request_headers(
                        "https://example.com/feed.xml", media_url, self.headers
                    )

    def test_same_origin_redirect_keeps_credentials(self):
        handler = _MediaRedirectHandler()
        request = urllib.request.Request(
            "https://example.com/audio.mp3", headers=self.headers
        )
        redirected = handler.redirect_request(
            request, None, 302, "Found", {},
            "https://example.com:443/new-audio.mp3",
        )
        self.assertEqual("Bearer private-feed-token", redirected.get_header("Authorization"))
        self.assertEqual("private", redirected.get_header("X-custom-secret"))

    def test_cross_origin_redirect_drops_all_custom_headers(self):
        handler = _MediaRedirectHandler()
        request = urllib.request.Request(
            "https://example.com/audio.mp3", headers=self.headers
        )
        redirected = handler.redirect_request(
            request, None, 302, "Found", {},
            "https://media.example.net/audio.mp3",
        )
        self.assertIsNone(redirected.get_header("Authorization"))
        self.assertIsNone(redirected.get_header("Cookie"))
        self.assertIsNone(redirected.get_header("X-custom-secret"))
        self.assertEqual("podcast-downloader", redirected.get_header("User-agent"))

    def test_redirect_to_new_origin_does_not_restore_prior_credentials(self):
        handler = _MediaRedirectHandler()
        first = urllib.request.Request(
            "https://example.com/audio.mp3", headers=self.headers
        )
        second = handler.redirect_request(
            first, None, 302, "Found", {}, "https://media.example.net/audio.mp3"
        )
        third = handler.redirect_request(
            second, None, 302, "Found", {}, "https://media.example.net/final.mp3"
        )
        self.assertIsNone(third.get_header("Authorization"))
        self.assertIsNone(third.get_header("X-custom-secret"))


if __name__ == "__main__":
    unittest.main()
