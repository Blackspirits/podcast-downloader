import json
from argparse import ArgumentParser
from pathlib import Path
from typing import Dict, List, Optional

def merge_parameters_collection(default: Dict, *others: Dict) -> Dict:
    """
    Merges multiple dictionaries into a new dictionary, starting with a default.

    Each subsequent dictionary in `others` will update the result, overwriting
    any existing keys. The original `default` dictionary is not modified.

    Args:
        default: The base dictionary.
        *others: A sequence of dictionaries to merge on top of the default.

    Returns:
        A new dictionary containing the merged key-value pairs.
    """
    result = default.copy()
    for other_dict in others:
        result.update(other_dict)
    return result


def load_configuration_file(file_path: Path) -> Dict:
    """
    Loads a configuration from a JSON file.

    Args:
        file_path: The Path object pointing to the configuration file.

    Returns:
        A dictionary with the loaded configuration.

    Raises:
        FileNotFoundError: If the specified file does not exist or is a directory.
        ValueError: If the file contains invalid JSON.
    """
    if not file_path.is_file():
        raise FileNotFoundError(f'Configuration file not found at "{file_path}"')

    try:
        with file_path.open(mode="r", encoding="utf-8") as json_file:
            return json.load(json_file)
    except json.JSONDecodeError as e:
        # Re-raise with a more user-friendly message
        raise ValueError(f'Failed to parse configuration file "{file_path}". It may be invalid JSON. Error: {e}') from e


def parse_argv(parser: ArgumentParser, args: Optional[List[str]] = None) -> Dict:
    """
    Parses command-line arguments and returns them as a dictionary.

    It filters out any arguments that were not explicitly set on the command line
    (i.e., those with a value of None).

    Args:
        parser: The ArgumentParser instance.
        args: An optional list of string arguments to parse.
              If None, `sys.argv` will be used.

    Returns:
        A dictionary of the provided command-line arguments and their values.
    """
    parsed_args = vars(parser.parse_args(args))
    return {key: value for key, value in parsed_args.items() if value is not None}
