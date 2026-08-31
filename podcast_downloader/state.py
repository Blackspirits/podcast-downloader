import hashlib
import json
import os
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit


STATE_FILE_NAME = ".podcast-downloader-state.json"
STATE_VERSION = 1


def empty_state():
    return {"version": STATE_VERSION, "episodes": {}}


def state_path(podcast_path: str) -> str:
    return os.path.join(podcast_path, STATE_FILE_NAME)


def load_state(podcast_path: str) -> dict:
    path = state_path(podcast_path)
    if not os.path.isfile(path):
        return empty_state()

    try:
        with open(path, mode="r", encoding="utf-8") as file:
            state = json.load(file)
    except (OSError, ValueError):
        return empty_state()

    if state.get("version") != STATE_VERSION or not isinstance(
        state.get("episodes"), dict
    ):
        return empty_state()

    return state


def save_state(podcast_path: str, state: dict) -> None:
    path = state_path(podcast_path)
    partial_path = path + ".part"

    with open(partial_path, mode="w", encoding="utf-8") as file:
        json.dump(state, file, indent=2, sort_keys=True)
        file.write("\n")

    os.replace(partial_path, path)


def normalize_episode_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path,
            parts.query,
            "",
        )
    )


def episode_identity(entity, feed_url: str) -> str:
    guid = getattr(entity, "guid", None)
    if guid:
        return "guid:" + str(guid).strip()

    link = getattr(entity, "link", None)
    if link:
        return "url:" + normalize_episode_url(link)

    published_date = getattr(entity, "published_date", None)
    title = getattr(entity, "title", "") or ""
    raw = "\0".join(
        (
            feed_url or "",
            repr(published_date),
            title,
        )
    )
    return "hash:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_episode(state: dict, identity: str):
    return state["episodes"].get(identity)


def mark_episode(state: dict, identity: str, entity, file_name: str) -> None:
    state["episodes"][identity] = {
        "url": getattr(entity, "link", None),
        "filename": file_name,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
    }
