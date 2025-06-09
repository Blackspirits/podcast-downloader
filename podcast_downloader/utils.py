# podcast_downloader/utils.py (Advanced Coloring Engine)

import logging
import re
from functools import reduce
from typing import Callable, Any, List, Tuple

class ConsoleOutputFormatter(logging.Formatter):
    """
    An advanced logging formatter that uses regular expressions to apply
    Catppuccin Mocha colors to specific keywords within log messages.
    """
    # Using TrueColor (24-bit) codes for maximum color fidelity
    RESET = "\033[0m"

    # --- Catppuccin Mocha Palette ---
    # https://github.com/catppuccin/catppuccin
    RED = "\033[38;2;243;139;168m"      # Error
    PEACH = "\033[38;2;250;179;135m"    # Warning
    YELLOW = "\033[38;2;249;226;175m"  # Data, paths, names
    GREEN = "\033[38;2;166;227;161m"    # Success, completion
    TEAL = "\033[38;2;148;226;213m"     # Actions, status
    SAPPHIRE = "\033[38;2;116;199;236m" # Default INFO color
    SUBTEXT0 = "\033[38;2;166;173;200m" # DEBUG
    OVERLAY0 = "\033[38;2;108;112;134m" # Timestamp

    # The list of rules to apply. Each rule is a tuple of (regex_pattern, color).
    # The regex pattern should contain one capturing group (...) for the part to be colored.
    # The rules are applied in order.
    COLORING_RULES: List[Tuple[str, str]] = [
        (r'(Loading configuration from file:)', TEAL),
        (r'(Checking)', TEAL),
        (r'(Last considered downloaded file:)', TEAL),
        (r'(Nothing new to download\.)', GREEN),
        (r'(Finished\.)', GREEN),
        # This rule finds any text inside double quotes
        (r'(".*?")', YELLOW),
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

        # Start with the default color for the log level
        level_color = {
            logging.DEBUG: self.SUBTEXT0,
            logging.INFO: self.SAPPHIRE,
            logging.WARNING: self.PEACH,
            logging.ERROR: self.RED,
        }.get(record.levelno, self.SAPPHIRE)
        
        # Apply specific keyword coloring rules
        formatted_message = message
        for pattern, color in self.COLORING_RULES:
            # The replacement function wraps the found group (the part in parentheses)
            # with the specified color codes.
            formatted_message = re.sub(
                pattern,
                lambda m: f"{color}{m.group(1)}{level_color}",
                formatted_message
            )

        # The final message is wrapped in the default level color
        # Parts of it may have been overridden by the rules above.
        final_message = f"{level_color}{formatted_message}{self.RESET}"

        if record.exc_info:
            final_message += "\n" + self.formatException(record.exc_info)

        return f"[{self.OVERLAY0}{timestamp}{self.RESET}] {final_message}"


def compose(*functions: Callable[[Any], Any]) -> Callable[[Any], Any]:
    """Composes single-argument functions from right to left."""
    return reduce(lambda f, g: lambda x: f(g(x)), functions)
