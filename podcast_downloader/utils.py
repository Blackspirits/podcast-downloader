# podcast_downloader/utils.py (Final Version with Catppuccin Mocha Theme)

import logging
import re
from functools import reduce
from typing import Callable, Any, List, Tuple

class ConsoleOutputFormatter(logging.Formatter):
    """
    An advanced logging formatter that uses regular expressions and special cases
    to apply Catppuccin Mocha colors to log messages.
    """
    # Using TrueColor (24-bit) codes for maximum color fidelity
    RESET = "\033[0m"

    # --- Catppuccin Mocha Palette ---
    RED = "\033[38;2;243;139;168m"      # Error
    GREEN = "\033[38;2;166;227;161m"    # Success
    YELLOW = "\033[38;2;249;226;175m"  # Warning
    BLUE = "\033[38;2;137;180;250m"     # Default INFO
    CYAN = "\033[38;2;148;226;213m"     # Actions
    WHITE = "\033[38;2;186;194;222m"    # Timestamp text
    BRIGHT_BLACK = "\033[38;2;88;91;112m" # DEBUG text & Timestamp brackets
    ROSEWATER = "\033[38;2;245;224;220m" # Quoted Filenames
    PINK = "\033[38;2;245;194;231m"     # Config Path
    MAUVE = "\033[38;2;203;166;247m"    # 'Nothing new' message
    LAVENDER = "\033[38;2;180;190;254m" # "saved as" text
    SKY = "\033[38;2;137;220;235m"      # Links/URLs & 'Last downloaded'

    # Dictionary mapping log levels to color constants
    LEVEL_COLORS = {
        logging.DEBUG: BRIGHT_BLACK,
        logging.INFO: BLUE,
        logging.WARNING: YELLOW,
        logging.ERROR: RED,
    }

    # General rules for simple log messages
    KEYWORD_RULES: List[Tuple[str, str]] = [
        (r'(Loading configuration from file:)', CYAN),
        (r'(Checking)', CYAN),
        (r'(Last downloaded file:)', SKY),
        (r'(Downloading new episode...)', CYAN),
        (r'(".*?")', ROSEWATER),
        (r'(Finished\.)', GREEN),
        (r'(Nothing new\.)', MAUVE),
        (r'(    -> Source URL:)', LAVENDER),
        (r'(    -> Saved as:)', LAVENDER),
    ]

 def __init__(self) -> None:
        """Initializes the formatter."""
        super().__init__(fmt="{message}", datefmt="%Y-%m-%d %H:%M:%S", style='{')

    def format(self, record: logging.LogRecord) -> str:
        """Formats the log record by applying keyword-based coloring rules."""
        timestamp = self.formatTime(record, self.datefmt)
        message = record.msg.format(*record.args) if record.args else record.msg
        
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
            f"{self.BRIGHT_BLACK}[{self.RESET}"
            f"{self.WHITE}{timestamp}{self.RESET}"
            f"{self.BRIGHT_BLACK}]{self.RESET} "
            f"{formatted_message}"
        )


def compose(*functions: Callable[[Any], Any]) -> Callable[[Any], Any]:
    """Composes single-argument functions from right to left."""
    return reduce(lambda f, g: lambda x: f(g(x)), functions)
