import hashlib
import os
import re
import unicodedata


DEFAULT_FILE_NAME_LIMIT = 255
INVALID_FILE_NAME_CHARACTERS = re.compile(r'[\u0000-\u001F\u007F\\/:*?"<>|]')
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def utf8_size(value: str) -> int:
    return len(value.encode("utf-8"))


def fit_utf8_prefix(value: str, maximum_bytes: int) -> str:
    if maximum_bytes <= 0:
        return ""

    result = []
    current_size = 0
    for character in value:
        character_size = utf8_size(character)
        if current_size + character_size > maximum_bytes:
            break
        result.append(character)
        current_size += character_size
    return "".join(result)


def stable_suffix(key: str) -> str:
    digest = hashlib.sha256(str(key).encode("utf-8")).hexdigest()[:8]
    return "~" + digest


def sanitize_file_component(value: str) -> str:
    value = unicodedata.normalize("NFC", value or "")
    value = INVALID_FILE_NAME_CHARACTERS.sub(" ", value)
    value = value.strip().rstrip(" .")

    stem, extension = os.path.splitext(value)
    if stem.upper() in WINDOWS_RESERVED_NAMES:
        value = "_" + value

    return value


def add_identity_suffix(file_name: str, identity: str) -> str:
    stem, extension = os.path.splitext(file_name)
    suffix = stable_suffix(identity)
    if stem.endswith(suffix):
        return file_name
    return stem + suffix + extension


def truncate_file_name(file_name: str, maximum_bytes: int, identity: str) -> str:
    if utf8_size(file_name) <= maximum_bytes:
        return file_name

    stem, extension = os.path.splitext(file_name)
    suffix = stable_suffix(identity)
    extension_size = utf8_size(extension)
    suffix_size = utf8_size(suffix)
    available_for_stem = maximum_bytes - extension_size - suffix_size

    if available_for_stem <= 0:
        fallback = "episode" + suffix + extension
        return fit_utf8_prefix(fallback, maximum_bytes)

    stem = fit_utf8_prefix(stem, available_for_stem).rstrip(" .")
    return stem + suffix + extension


def finalize_file_name(raw_file_name: str, maximum_bytes: int, identity: str) -> str:
    normalized = unicodedata.normalize("NFC", raw_file_name or "").strip()
    sanitized = sanitize_file_component(normalized)

    if not sanitized:
        sanitized = "episode" + stable_suffix(identity)
    elif sanitized != normalized:
        sanitized = add_identity_suffix(sanitized, identity)

    return truncate_file_name(sanitized, maximum_bytes, identity)


def get_file_name_limit(directory: str) -> int:
    if os.name == "nt":
        return DEFAULT_FILE_NAME_LIMIT

    try:
        return int(os.pathconf(directory, "PC_NAME_MAX"))
    except (AttributeError, OSError, ValueError):
        return DEFAULT_FILE_NAME_LIMIT


def safe_destination_path(directory: str, file_name: str) -> str:
    base = os.path.abspath(directory)
    destination = os.path.abspath(os.path.join(base, file_name))

    if os.path.commonpath((base, destination)) != base:
        raise ValueError("Podcast file path escapes the configured directory")

    return destination
