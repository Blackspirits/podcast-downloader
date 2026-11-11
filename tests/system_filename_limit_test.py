import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from podcast_downloader.__main__ import get_system_file_name_limit
from podcast_downloader.rss import limit_file_name


class SystemFilenameLimitTest(unittest.TestCase):
    def test_long_posix_directory_does_not_collapse_all_filenames(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            while len(str(target)) <= 280:
                target /= "nested-podcast-folders"
                target.mkdir()
            with patch("podcast_downloader.__main__.is_windows_running", return_value=False):
                limit = get_system_file_name_limit({"path": str(target)})

            self.assertGreaterEqual(limit, 200)
            self.assertGreater(limit, 0)
            self.assertNotEqual(
                limit_file_name(limit, "first-episode.mp3"),
                limit_file_name(limit, "second-episode.mp3"),
            )

    def test_posix_uses_name_max_from_filesystem(self):
        with patch("podcast_downloader.__main__.is_windows_running", return_value=False):
            with patch("podcast_downloader.__main__.os.pathconf", return_value=120):
                self.assertEqual(
                    120,
                    get_system_file_name_limit({"path": "/some/existing/path"}),
                )

    def test_posix_pathconf_failure_uses_safe_fallback(self):
        with patch("podcast_downloader.__main__.is_windows_running", return_value=False):
            with patch("podcast_downloader.__main__.os.pathconf", side_effect=OSError):
                self.assertEqual(
                    255,
                    get_system_file_name_limit({"path": "/missing/path"}),
                )

    def test_windows_accounts_for_directory_and_separator(self):
        path = "C:\\podcasts\\" + "folder" * 33
        with patch("podcast_downloader.__main__.is_windows_running", return_value=True):
            with patch("podcast_downloader.__main__.os.path.abspath", return_value=path):
                remaining = get_system_file_name_limit({"path": "not-important"})
        self.assertEqual(259 - len(path) - 1, remaining)
        self.assertLess(remaining, 255)

    def test_windows_fails_loudly_when_path_is_too_long(self):
        path = "C:\\" + "x" * 270
        with patch("podcast_downloader.__main__.is_windows_running", return_value=True):
            with patch("podcast_downloader.__main__.os.path.abspath", return_value=path):
                with self.assertRaisesRegex(ValueError, "too long"):
                    get_system_file_name_limit({"path": "ignored"})

    def test_unicode_utf8_basename_fits_in_byte_limit(self):
        limit = 255
        result = limit_file_name(limit, ("é" * 200) + ".mp3")
        self.assertTrue(result.endswith(".mp3"))
        self.assertLessEqual(len(os.fsencode(result)), limit)
        self.assertGreater(len(result), 0)

    def test_unicode_emoji_not_split_and_suffix_preserved(self):
        result = limit_file_name(20, "😀" * 20 + ".mp3")
        self.assertTrue(result.endswith(".mp3"))
        self.assertLessEqual(len(os.fsencode(result)), 20)
        self.assertNotIn("\ufffd", result)

    def test_windows_utf16_code_unit_limit_for_emoji(self):
        with patch("podcast_downloader.rss.sys.platform", "win32"):
            result = limit_file_name(10, "😀" * 20 + ".mp3")
        self.assertEqual("😀" * 3 + ".mp3", result)

    def test_negative_filename_limit_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "positive"):
            limit_file_name(-81, "episode.mp3")

    def test_extension_longer_than_limit_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "extension"):
            limit_file_name(2, "episode.mp3")

    def test_ascii_behavior_remains_compatible(self):
        self.assertEqual("123456.mp3", limit_file_name(10, "123456789012345.mp3"))
        self.assertEqual("1.mp3", limit_file_name(5, "1234.mp3"))


if __name__ == "__main__":
    unittest.main()
