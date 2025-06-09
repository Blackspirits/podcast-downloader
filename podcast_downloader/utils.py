# podcast_downloader/utils.py (Final Version with Catppuccin Mocha Theme)

import logging
import re
from functools import reduce
from typing import Callable, Any, List, Tuple

class ConsoleOutputFormatter(logging.Formatter):
    """
    An advanced logging formatter that uses regular expressions to apply
    Catppuccin Mocha colors based on a terminal color scheme.
    """
    # Using TrueColor (24-bit) codes for maximum color fidelity
    RESET = "\033[0m"

    # --- Catppuccin Mocha Palette (from user's JSON scheme) ---
    # https://github.com/catppuccin/catppuccin
    RED = "\033[38;2;243;139;168m"      # #F38BA8
    GREEN = "\033[38;2;166;227;161m"    # #A6E3A1
    YELLOW = "\033[38;2;249;226;175m"  # #F9E2AF
    BLUE = "\033[38;2;137;180;250m"     # #89B4FA
    CYAN = "\033[38;2;148;226;213m"     # #94E2D5 (mapped from Teal)
    WHITE = "\033[38;2;186;194;222m"    # #BAC2DE (Subtext1, for Timestamp)
    BRIGHT_BLACK = "\033[38;2;88;91;112m" # #585B70 (for DEBUG)
    ROSEWATER = "\033[38;2;245;224;220m" # #f5e0dc (for file paths)

    # Dictionary mapping log levels to the new color constants
    LEVEL_COLORS = {
        logging.DEBUG: BRIGHT_BLACK,
        logging.INFO: BLUE,
        logging.WARNING: YELLOW,
        logging.ERROR: RED,
    }

    # Rules for applying specific colors to keywords inside a message
    KEYWORD_RULES: List[Tuple[str, str]] = [
        (r'(Loading configuration from file:|Checking|Last considered downloaded file:)', CYAN),
        (r'(".*?")', ROSEWATER), # CHANGED: Text in quotation marks is now Rosewater
        (r'(Finished\.)', GREEN),
    ]

    def __init__(self) -> None:
        """Initializes the formatter."""
        super().__init__(fmt="{message}", datefmt="%Y-%m-%d %H:%M:%S", style='{')

    def format(self, record: logging.LogRecord) -> str:
        """Formats the log record by applying keyword-based coloring rules."""
        timestamp = self.formatTime(record, self.datefmt)

        if record.args:
            message = record.msg.format(*record.args)
        else:
            message = record.msg
        
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

        return f"[{self.WHITE}{timestamp}{self.RESET}] {formatted_message}"


def compose(*functions: Callable[[Any], Any]) -> Callable[[Any], Any]:
    """Composes single-argument functions from right to left."""
    return reduce(lambda f, g: lambda x: f(g(x)), functions)
