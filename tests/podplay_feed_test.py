import time
import unittest

import feedparser

from podcast_downloader.rss import (
    add_podplay_entries,
    flatten_rss_links_data,
    get_podplay_entries,
)


PP_NAMESPACE = "https://example.com/podplay"


def build_feed(custom_episodes: str, standard_url="https://example.com/standard.mp3"):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:pp="{PP_NAMESPACE}">
  <channel>
    <title>Podplay feed</title>
    <item>
      <title>Standard episode</title>
      <pubDate>Fri, 23 Oct 2020 19:16:10 +0000</pubDate>
      <enclosure url="{standard_url}" length="1" type="audio/mpeg"/>
    </item>
    {custom_episodes}
  </channel>
</rss>
""".encode("utf-8")


def podplay_episode(url: str, published: str, title="Custom episode", mimetype="audio/mpeg"):
    return f"""
<pp:episode>
  <pp:url>{url}</pp:url>
  <pp:mimetype>{mimetype}</pp:mimetype>
  <pp:pubdate>{published}</pp:pubdate>
  <pp:title>{title}</pp:title>
</pp:episode>
"""


class PodplayFeedTest(unittest.TestCase):
    def test_podplay_episodes_are_added_to_standard_feed_entries(self):
        xml = build_feed(
            podplay_episode(
                "https://example.com/custom-one.mp3",
                "1603396907",
                "Custom one",
            )
            + podplay_episode(
                "https://example.com/custom-two.mp3",
                "1603309056",
                "Custom two",
            )
        )
        feed = add_podplay_entries(feedparser.parse(xml), xml)

        entities = list(flatten_rss_links_data(iter(feed.entries)))

        self.assertEqual(
            ["Standard episode", "Custom one", "Custom two"],
            [entry.title for entry in entities],
        )
        self.assertEqual(
            [
                "https://example.com/standard.mp3",
                "https://example.com/custom-one.mp3",
                "https://example.com/custom-two.mp3",
            ],
            [entry.link for entry in entities],
        )
        self.assertEqual(time.gmtime(1603396907), entities[1].published_date)

    def test_invalid_or_incomplete_podplay_episodes_are_skipped(self):
        xml = build_feed(
            podplay_episode("https://example.com/good.mp3", "1603396907")
            + podplay_episode("https://example.com/bad-date.mp3", "not-a-timestamp")
            + """
<pp:episode>
  <pp:mimetype>audio/mpeg</pp:mimetype>
  <pp:pubdate>1603309056</pp:pubdate>
  <pp:title>Missing URL</pp:title>
</pp:episode>
"""
        )

        entries = get_podplay_entries(xml)

        self.assertEqual(1, len(entries))
        self.assertEqual("https://example.com/good.mp3", entries[0].links[0].href)

    def test_unescaped_ampersands_in_podplay_urls_are_preserved(self):
        url = (
            "https://example.com/custom.mp3?aw_0_1st.episodeid=139171"
            "&aw_0_1st.collectionid=3233"
        )
        xml = build_feed(podplay_episode(url, "1603396907"))

        entries = get_podplay_entries(xml)

        self.assertEqual(1, len(entries))
        self.assertEqual(url, entries[0].links[0].href)

    def test_existing_standard_enclosure_is_not_added_twice(self):
        shared_url = "https://example.com/shared.mp3"
        xml = build_feed(
            podplay_episode(shared_url, "1603396907"), standard_url=shared_url
        )
        feed = add_podplay_entries(feedparser.parse(xml), xml)

        entities = list(flatten_rss_links_data(iter(feed.entries)))

        self.assertEqual(1, len(entities))
        self.assertEqual(shared_url, entities[0].link)

    def test_other_namespace_episode_elements_are_ignored(self):
        xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:custom="https://example.com/custom">
  <channel>
    <title>Other extension</title>
    <custom:episode>
      <custom:url>https://example.com/not-podplay.mp3</custom:url>
      <custom:mimetype>audio/mpeg</custom:mimetype>
      <custom:pubdate>1603396907</custom:pubdate>
      <custom:title>Not Podplay</custom:title>
    </custom:episode>
  </channel>
</rss>
"""

        self.assertEqual([], get_podplay_entries(xml))


if __name__ == "__main__":
    unittest.main()
