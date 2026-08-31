import time
import unittest

from podcast_downloader.__main__ import (
    bootstrap_episode_state,
    select_missing_entries,
)
from podcast_downloader.rss import RSSEntity
from podcast_downloader.state import (
    empty_state,
    episode_identity,
    get_episode,
    mark_episode,
)


FEED_URL = "https://example.com/feed.xml"


def entity(name, day, guid):
    return RSSEntity(
        time.strptime(f"2026-08-{day:02d}", "%Y-%m-%d"),
        name,
        "audio/mpeg",
        f"https://example.com/{name}.mp3",
        guid,
    )


class StateSelectionTest(unittest.TestCase):
    def test_existing_file_is_migrated_into_state(self):
        episode = entity("existing", 1, "guid-existing")
        state = empty_state()

        changed = bootstrap_episode_state(
            state,
            [episode],
            ["existing.mp3"],
            lambda _: "existing.mp3",
            FEED_URL,
        )

        self.assertTrue(changed)
        self.assertEqual(
            "existing.mp3",
            get_episode(state, episode_identity(episode, FEED_URL))["filename"],
        )

    def test_filename_template_change_does_not_redownload_known_episode(self):
        episode = entity("episode", 1, "guid-1")
        state = empty_state()
        mark_episode(state, episode_identity(episode, FEED_URL), episode, "old-name.mp3")

        missing, boundary = select_missing_entries(
            state,
            [episode],
            ["old-name.mp3"],
            FEED_URL,
            False,
            lambda entries: entries,
        )

        self.assertEqual([], missing)
        self.assertEqual(episode, boundary)

    def test_new_episode_before_known_boundary_is_selected(self):
        newest = entity("new", 2, "guid-new")
        known = entity("known", 1, "guid-known")
        state = empty_state()
        mark_episode(state, episode_identity(known, FEED_URL), known, "known.mp3")

        missing, boundary = select_missing_entries(
            state,
            [newest, known],
            ["known.mp3"],
            FEED_URL,
            False,
            lambda entries: entries,
        )

        self.assertEqual([newest], missing)
        self.assertEqual(known, boundary)

    def test_fill_up_gaps_selects_missing_episode_inside_history(self):
        newest = entity("newest", 3, "guid-newest")
        gap = entity("gap", 2, "guid-gap")
        oldest = entity("oldest", 1, "guid-oldest")
        state = empty_state()
        mark_episode(
            state, episode_identity(newest, FEED_URL), newest, "newest.mp3"
        )
        mark_episode(
            state, episode_identity(oldest, FEED_URL), oldest, "oldest.mp3"
        )

        missing, boundary = select_missing_entries(
            state,
            [newest, gap, oldest],
            ["newest.mp3", "oldest.mp3"],
            FEED_URL,
            True,
            lambda entries: entries,
        )

        self.assertEqual([gap], missing)
        self.assertEqual(oldest, boundary)


if __name__ == "__main__":
    unittest.main()
