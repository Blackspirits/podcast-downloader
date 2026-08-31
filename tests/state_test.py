import os
import tempfile
import time
import unittest

from podcast_downloader.rss import RSSEntity
from podcast_downloader.state import (
    STATE_FILE_NAME,
    episode_identity,
    get_episode,
    load_state,
    mark_episode,
    save_state,
)


class EntityWithGuid:
    def __init__(self, guid, link):
        self.guid = guid
        self.link = link
        self.published_date = time.gmtime()
        self.title = "Episode"


class EpisodeStateTest(unittest.TestCase):
    def test_guid_is_preferred_over_url(self):
        entity = EntityWithGuid("abc-123", "HTTPS://Example.com/episode.mp3#fragment")

        self.assertEqual(
            "guid:abc-123", episode_identity(entity, "https://example.com/feed.xml")
        )

    def test_url_is_used_when_guid_is_missing(self):
        entity = RSSEntity(
            time.gmtime(),
            "Episode",
            "audio/mpeg",
            "HTTPS://Example.com/episode.mp3?token=1#fragment",
        )

        self.assertEqual(
            "url:https://example.com/episode.mp3?token=1",
            episode_identity(entity, "https://example.com/feed.xml"),
        )

    def test_state_is_saved_atomically_and_loaded_again(self):
        entity = RSSEntity(
            time.gmtime(),
            "Episode",
            "audio/mpeg",
            "https://example.com/episode.mp3",
        )

        with tempfile.TemporaryDirectory() as directory:
            state = load_state(directory)
            identity = episode_identity(entity, "https://example.com/feed.xml")
            mark_episode(state, identity, entity, "episode.mp3")
            save_state(directory, state)

            loaded = load_state(directory)

            self.assertEqual("episode.mp3", get_episode(loaded, identity)["filename"])
            self.assertTrue(os.path.isfile(os.path.join(directory, STATE_FILE_NAME)))
            self.assertFalse(
                os.path.exists(os.path.join(directory, STATE_FILE_NAME + ".part"))
            )


if __name__ == "__main__":
    unittest.main()
