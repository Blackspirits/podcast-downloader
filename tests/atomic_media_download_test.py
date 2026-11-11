import io
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from podcast_downloader.__main__ import (
    DOWNLOAD_CHUNK_SIZE,
    _save_response_atomically,
    download_rss_entity_to_path,
)
from podcast_downloader.rss import RSSEntity


class TrackingResponse(io.BytesIO):
    def __init__(self, body, content_length=None):
        super().__init__(body)
        self.read_sizes = []
        self.headers = (
            {"Content-Length": str(content_length)}
            if content_length is not None
            else {}
        )

    def read(self, size=-1):
        self.read_sizes.append(size)
        return super().read(size)


class InterruptedResponse(TrackingResponse):
    def __init__(self, body):
        super().__init__(body)
        self.calls = 0

    def read(self, size=-1):
        self.calls += 1
        if self.calls == 2:
            raise IOError("connection interrupted")
        return super().read(size)


class AtomicMediaDownloadTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.destination = Path(self.tmp.name) / "episode.mp3"
        self.episode = RSSEntity(
            time.gmtime(0), "Episode", "audio/mpeg",
            "https://example.com/episode.mp3",
        )

    def part_files(self):
        return list(Path(self.tmp.name).glob(".podcast-downloader-*.part"))

    def test_success_writes_in_chunks_and_publishes_final_file(self):
        data = b"audio" * (DOWNLOAD_CHUNK_SIZE // 3)
        response = TrackingResponse(data, content_length=len(data))

        with patch(
            "podcast_downloader.__main__._open_media_request",
            return_value=response,
        ):
            download_rss_entity_to_path(
                {}, "https://example.com/feed.xml",
                lambda _: "episode.mp3", self.tmp.name, self.episode
            )

        self.assertEqual(data, self.destination.read_bytes())
        self.assertEqual([], self.part_files())
        self.assertTrue(response.read_sizes)
        self.assertEqual({DOWNLOAD_CHUNK_SIZE}, set(response.read_sizes))
        self.assertGreater(len(response.read_sizes), 1)

    def test_interrupted_stream_does_not_replace_existing_valid_file(self):
        self.destination.write_bytes(b"existing-valid-file")
        response = InterruptedResponse(b"partial audio")
        with patch(
            "podcast_downloader.__main__._open_media_request",
            return_value=response,
        ), patch("podcast_downloader.__main__.logger") as logger:
            download_rss_entity_to_path(
                {}, "https://example.com/feed.xml",
                lambda _: "episode.mp3", self.tmp.name, self.episode
            )
            logger.exception.assert_called_once()

        self.assertEqual(b"existing-valid-file", self.destination.read_bytes())
        self.assertEqual([], self.part_files())

    def test_interrupted_stream_does_not_leave_new_file(self):
        response = InterruptedResponse(b"partial audio")
        with patch(
            "podcast_downloader.__main__._open_media_request",
            return_value=response,
        ), patch("podcast_downloader.__main__.logger") as logger:
            download_rss_entity_to_path(
                {}, "https://example.com/feed.xml",
                lambda _: "episode.mp3", self.tmp.name, self.episode
            )
            logger.exception.assert_called_once()

        self.assertFalse(self.destination.exists())
        self.assertEqual([], self.part_files())

    def test_short_response_with_content_length_is_rejected(self):
        self.destination.write_bytes(b"previous-data")
        response = TrackingResponse(b"short", content_length=1000)

        with self.assertRaisesRegex(IOError, "Incomplete media response"):
            _save_response_atomically(response, str(self.destination))

        self.assertEqual(b"previous-data", self.destination.read_bytes())
        self.assertEqual([], self.part_files())

    def test_zero_byte_response_is_not_published(self):
        with self.assertRaisesRegex(IOError, "Empty media response"):
            _save_response_atomically(
                TrackingResponse(b"", content_length=0), str(self.destination)
            )
        self.assertFalse(self.destination.exists())
        self.assertEqual([], self.part_files())

    def test_failed_atomic_replace_cleans_up_partial_file(self):
        self.destination.write_bytes(b"previous-data")
        with patch(
            "podcast_downloader.__main__.os.replace",
            side_effect=OSError("disk full"),
        ):
            with self.assertRaisesRegex(OSError, "disk full"):
                _save_response_atomically(
                    TrackingResponse(b"new audio", content_length=9),
                    str(self.destination),
                )
        self.assertEqual(b"previous-data", self.destination.read_bytes())
        self.assertEqual([], self.part_files())

    def test_temporary_file_is_created_beside_destination(self):
        response = TrackingResponse(b"new audio", content_length=9)
        observed = []
        original_replace = os.replace

        def capture_replace(src, dst):
            observed.append((src, dst))
            return original_replace(src, dst)

        with patch(
            "podcast_downloader.__main__.os.replace",
            side_effect=capture_replace,
        ):
            _save_response_atomically(response, str(self.destination))

        self.assertEqual(1, len(observed))
        self.assertEqual(self.tmp.name, os.path.dirname(observed[0][0]))
        self.assertEqual(str(self.destination), observed[0][1])
        self.assertEqual([], self.part_files())


if __name__ == "__main__":
    unittest.main()
