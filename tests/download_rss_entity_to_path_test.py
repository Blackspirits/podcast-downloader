import io
import os
import tempfile
import time
import unittest
from email.message import Message
from unittest.mock import Mock, patch

import podcast_downloader.__main__ as main
from podcast_downloader.rss import RSSEntity


class FakeResponse(io.BytesIO):
    def __init__(self, data: bytes, content_type="audio/mpeg", content_length=None):
        super().__init__(data)
        self.headers = Message()
        self.headers["Content-Type"] = content_type
        if content_length is not None:
            self.headers["Content-Length"] = str(content_length)
        self.read_sizes = []

    def read(self, size=-1):
        self.read_sizes.append(size)
        if size == -1:
            raise AssertionError("download should be streamed in chunks")
        return super().read(size)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


class InterruptedResponse(FakeResponse):
    def __init__(self):
        super().__init__(b"partial data")
        self.calls = 0

    def read(self, size=-1):
        self.calls += 1
        if self.calls == 1:
            return b"partial"
        raise OSError("connection interrupted")


class DownloadRssEntityToPathTest(unittest.TestCase):
    def setUp(self):
        main.logger = Mock()
        self.entity = RSSEntity(
            published_date=time.gmtime(),
            title="Episode",
            type="audio/mpeg",
            link="https://example.com/episode.mp3",
        )
        self.to_file_name = lambda _: "episode.mp3"

    def test_download_is_streamed_and_atomically_moved_into_place(self):
        response = FakeResponse(b"podcast data", content_length=12)

        with tempfile.TemporaryDirectory() as directory:
            with patch("urllib.request.urlopen", return_value=response) as urlopen:
                result = main.download_rss_entity_to_path(
                    {}, self.to_file_name, directory, self.entity
                )

            self.assertTrue(result)
            with open(os.path.join(directory, "episode.mp3"), "rb") as file:
                self.assertEqual(b"podcast data", file.read())
            self.assertFalse(os.path.exists(os.path.join(directory, "episode.mp3.part")))
            self.assertTrue(all(size > 0 for size in response.read_sizes))
            self.assertEqual(
                main.DOWNLOAD_TIMEOUT_SECONDS, urlopen.call_args.kwargs["timeout"]
            )

    def test_interrupted_download_does_not_leave_final_or_partial_file(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("urllib.request.urlopen", return_value=InterruptedResponse()):
                result = main.download_rss_entity_to_path(
                    {}, self.to_file_name, directory, self.entity
                )

            self.assertFalse(result)
            self.assertFalse(os.path.exists(os.path.join(directory, "episode.mp3")))
            self.assertFalse(os.path.exists(os.path.join(directory, "episode.mp3.part")))

    def test_content_length_mismatch_is_not_committed(self):
        response = FakeResponse(b"short", content_length=100)

        with tempfile.TemporaryDirectory() as directory:
            with patch("urllib.request.urlopen", return_value=response):
                result = main.download_rss_entity_to_path(
                    {}, self.to_file_name, directory, self.entity
                )

            self.assertFalse(result)
            self.assertFalse(os.path.exists(os.path.join(directory, "episode.mp3")))
            self.assertFalse(os.path.exists(os.path.join(directory, "episode.mp3.part")))

    def test_html_response_is_not_saved_as_podcast(self):
        response = FakeResponse(b"<html>login</html>", content_type="text/html")

        with tempfile.TemporaryDirectory() as directory:
            with patch("urllib.request.urlopen", return_value=response):
                result = main.download_rss_entity_to_path(
                    {}, self.to_file_name, directory, self.entity
                )

            self.assertFalse(result)
            self.assertFalse(os.path.exists(os.path.join(directory, "episode.mp3")))


if __name__ == "__main__":
    unittest.main()
