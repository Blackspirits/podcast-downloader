import os
import tempfile
import unittest

from podcast_downloader.filenames import (
    finalize_file_name,
    safe_destination_path,
    sanitize_file_component,
    utf8_size,
)


class FilenameSafetyTest(unittest.TestCase):
    def test_nfc_preserves_portuguese_ordinals(self):
        self.assertEqual("2º Cromo", sanitize_file_component("2º Cromo"))
        self.assertEqual("1ª Parte", sanitize_file_component("1ª Parte"))

    def test_invalid_characters_get_a_stable_collision_suffix(self):
        first = finalize_file_name("a/b.mp3", 255, "guid:first")
        second = finalize_file_name("a:b.mp3", 255, "guid:second")

        self.assertNotEqual(first, second)
        self.assertTrue(first.endswith(".mp3"))
        self.assertTrue(second.endswith(".mp3"))
        self.assertNotIn("/", first)
        self.assertNotIn(":", second)

    def test_windows_reserved_names_are_escaped(self):
        self.assertEqual("_CON.mp3", sanitize_file_component("CON.mp3"))
        self.assertEqual("_LPT1", sanitize_file_component("LPT1"))

    def test_truncation_respects_utf8_byte_limit_and_preserves_extension(self):
        result = finalize_file_name("á" * 200 + ".mp3", 64, "guid:long")

        self.assertLessEqual(utf8_size(result), 64)
        self.assertTrue(result.endswith(".mp3"))
        self.assertIn("~", result)

    def test_destination_cannot_escape_podcast_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                safe_destination_path(directory, "../episode.mp3")

    def test_valid_destination_stays_inside_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            result = safe_destination_path(directory, "episode.mp3")

            self.assertEqual(os.path.join(directory, "episode.mp3"), result)


if __name__ == "__main__":
    unittest.main()
