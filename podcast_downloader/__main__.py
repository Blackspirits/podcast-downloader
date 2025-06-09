# podcast_downloader/utils.py (Final and Definitive Version)

import logging
import re
from functools import reduce
from typing import Callable, Any, List, Tuple

class ConsoleOutputFormatter(logging.Formatter):
    """
    An advanced logging formatter that uses special cases and regular expressions
    to apply Catppuccin Mocha colors to log messages.
    """
    RESET = "\033[0m"

    # --- Catppuccin Mocha Palette - As per your final request ---
    RED = "\033[38;2;243;139;168m"      # Error
    GREEN = "\033[38;2;166;227;161m"    # Success
    YELLOW = "\033[38;2;249;226;175m"  # Warning
    BLUE = "\033[38;2;137;180;250m"     # Default INFO
    CYAN = "\033[38;2;148;226;213m"     # Actions
    WHITE = "\033[38;2;186;194;222m"    # Config Path Text
    BRIGHT_BLACK = "\033[38;2;88;91;112m" # DEBUG text
    ROSEWATER = "\033[38;2;245;224;220m" # Quoted Podcast Names/Data
    FLAMINGO = "\033[38;2;242;205;205m" # Timestamp text
    MAUVE = "\033[38;2;203;166;247m"    # 'Nothing new' message
    LAVENDER = "\033[38;2;180;190;254m" # "-> ..." text
    MAROON = "\033[38;2;235;160;172m"   # Filename on download line
    SKY = "\033[38;2;137;220;235m"      # Links/URLs
    OVERLAY2 = "\033[38;2;147;153;178m" # Timestamp Brackets
    PINK = "\033[38;2;245;194;231m"     # Used for config path quotes

    LEVEL_COLORS = {
        logging.DEBUG: BRIGHT_BLACK,
        logging.INFO: BLUE,
        logging.WARNING: YELLOW,
        logging.ERROR: RED,
    }
    
    # Cleaned up general rules for simple log messages
    KEYWORD_RULES: List[Tuple[str, str]] = [
        (r'(Checking)', BLUE),
        (r'(Last downloaded file:)', BLUE),
        (r'(".*?")', ROSEWATER),
        (r'(Finished\.)', GREEN),
        (r'(Nothing new to download\.)', MAUVE),
    ]

    def __init__(self) -> None:
        """Initializes the formatter."""
        super().__init__(fmt="{message}", datefmt="%Y-%m-%d %H:%M:%S", style='{')

    def format(self, record: logging.LogRecord) -> str:
        """Formats the log record by applying keyword-based coloring rules."""
        timestamp = self.formatTime(record, self.datefmt)
        message = record.msg.format(*record.args) if record.args else record.msg
        
        # Handle special cases first for full control over coloring
        if record.msg.startswith('Loading configuration from file:'):
            pattern = r'(Loading configuration from file: )(".*?")'
            formatted_message = re.sub(
                pattern,
                lambda m: f"{self.CYAN}{m.group(1)}{self.RESET}{self.WHITE}{m.group(2)}{self.RESET}",
                message
            )
        # This check is now synced with the correct __main__.py
        elif record.msg.startswith('{}: Downloading new episode...'):
            podcast_name, = record.args
            text_part = record.msg.replace('{}', f'"{podcast_name}"')
            formatted_message = f"{self.CYAN}Downloading new episode of: {self.RESET}{self.ROSEWATER}{text_part}{self.RESET}"
        
        elif record.msg.startswith('    -> Source URL:'):
            url, = record.args
            formatted_message = f"    {self.LAVENDER}-> Source URL:{self.RESET} {self.SKY}\"{url}\"{self.RESET}"

        elif record.msg.startswith('    -> Saved as:'):
            filename, = record.args
            formatted_message = f"    {self.LAVENDER}-> Saved as:{self.RESET} {self.MAROON}\"{filename}\"{self.RESET}"

        else:
            # For all other messages, use the general keyword rules
            default_color = self.LEVEL_COLORS.get(record.levelno, self.BLUE)
            formatted_message = f"{default_color}{message}{self.RESET}"
            
            for pattern, color in self.KEYWORD_RULES:
                 formatted_message = re.sub(
                    pattern,
                    lambda m: f"{color}{m.group(1)}{default_color}",
                    formatted_message
                )

        if record.exc_info:
            formatted_message += "\n" + self.formatException(record.exc_info)

        return (
            f"{self.OVERLAY2}[{self.RESET}"
            f"{self.FLAMINGO}{timestamp}{self.RESET}"
            f"{self.OVERLAY2}]{self.RESET} "
            f"{formatted_message}"
        )


def compose(*functions: Callable[[Any], Any]) -> Callable[[Any], Any]:
    """Composes single-argument functions from right to left."""
    return reduce(lambda f, g: lambda x: f(g(x)), functions)
