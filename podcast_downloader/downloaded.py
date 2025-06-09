from pathlib import Path
from typing import Callable, Iterable, List, Set

def get_extensions_checker(extensions: Iterable[str]) -> Callable[[str], bool]:
    """
    Creates a function that checks if a filename ends with one of the given extensions.

    Args:
        extensions: An iterable of file extensions (e.g., ['.mp3', '.m4a']).

    Returns:
        A function that takes a filename string and returns True if it has a valid extension.
    """
    # Using a tuple for the extensions makes the 'endswith' check slightly faster.
    valid_extensions = tuple(extensions)
    return lambda file_name: file_name.endswith(valid_extensions)


def get_sorted_files_from_directory(directory_path: Path) -> List[Path]:
    """
    Lists all files in a directory, sorted by creation time (newest first).

    Args:
        directory_path: The Path object of the directory to scan.

    Returns:
        A list of Path objects for each file, sorted from newest to oldest.
        Returns an empty list if the directory does not exist.
    """
    try:
        # Filter for files only and sort by creation time
        files = [p for p in directory_path.iterdir() if p.is_file()]
        files.sort(key=lambda p: p.stat().st_ctime, reverse=True)
        return files
    except FileNotFoundError:
        # If the directory doesn't exist, there are no files in it.
        return []


def get_downloaded_files(
    podcast_files_filter: Callable[[str], bool], podcast_directory: Path
) -> Iterable[str]:
    """
    Gets a list of already downloaded podcast files from a directory.

    Args:
        podcast_files_filter: A function that returns True if a filename is a valid podcast file.
        podcast_directory: The Path to the directory where podcasts are stored.

    Returns:
        A generator that yields the filenames of downloaded podcast files.
    """
    # The generator expression is memory-efficient.
    return (
        path.name
        for path in get_sorted_files_from_directory(podcast_directory)
        if podcast_files_filter(path.name)
    )


def get_last_downloaded_file_before_gap(
    feed_files: List[str], downloaded_files: Iterable[str]
) -> str:
    """
    Finds the last successfully downloaded file in a sequence before a missing file (a "gap").

    This helps in resuming downloads to fill in missing episodes instead of only
    downloading the newest ones.

    Args:
        feed_files: A list of all filenames as they appear in the RSS feed (ordered).
        downloaded_files: An iterable of filenames that exist on disk.

    Returns:
        The filename of the last downloaded file before the first gap, or None if no gaps are found
        after the first downloaded file.
    """
    last_seen_downloaded_file = None
    # Using a set provides fast O(1) average time complexity for lookups.
    all_downloaded_files: Set[str] = set(downloaded_files)

    for feed_file_name in feed_files:
        if feed_file_name in all_downloaded_files:
            last_seen_downloaded_file = feed_file_name
        else:
            # We found a file from the feed that is NOT downloaded.
            # If we have seen a downloaded file before this one, it's the one before the gap.
            if last_seen_downloaded_file is not None:
                return last_seen_downloaded_file

    # If the loop completes, it means there were no gaps after the first downloaded file.
    # We return the last file we saw, which will be the latest downloaded file in the feed.
    return last_seen_downloaded_file
