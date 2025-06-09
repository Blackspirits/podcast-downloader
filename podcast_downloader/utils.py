# podcast_downloader/utils.py (with Catppuccin Mocha Colors)

import logging
from functools import reduce
from typing import Callable, Any

class ConsoleOutputFormatter(logging.Formatter):
    """
    A custom logging formatter that adds Catppuccin Mocha colors to the terminal output.
    """
    # Using TrueColor (24-bit) codes for maximum color fidelity
    # Format: \033[38;2;R;G;Bm
    RESET = "\033[0m"

    # Catppuccin Mocha palette colors
    # https://github.com/catppuccin/catppuccin
    COLORS = {
        # DEBUG: Subtext0 (#a6adc8)
        logging.DEBUG: "\033[38;2;166;173;200m",
        # INFO: Sapphire (#74c7ec)
        logging.INFO: "\033[38;2;116;199;236m",
        # WARNING: Peach (#fab387)
        logging.WARNING: "\033[38;2;250;179;135m",
        # ERROR: Red (#f38ba8)
        logging.ERROR: "\033[38;2;243;139;168m",
    }
    
    # DATE_COLOR: Overlay0 (#6c7086)
    DATE_COLOR = "\033[38;2;108;112;134m"


    def __init__(self) -> None:
        """
        Initializes the formatter using '{'-style formatting.
        """
        super().__init__(
            fmt="{message}",
            datefmt="%Y-%m-%d %H:%M:%S",
            style='{'
        )

    def format(self, record: logging.LogRecord) -> str:
        """
        Formats the log record with the appropriate colors.
        """
        level_color = self.COLORS.get(record.levelno, self.RESET)
        timestamp = self.formatTime(record, self.datefmt)

        if record.args:
            message = record.msg.format(*record.args)
        else:
            message = record.msg

        if record.exc_info:
            message += "\n" + self.formatException(record.exc_info)

        return (
            f"[{self.DATE_COLOR}{timestamp}{self.RESET}] "
            f"{level_color}{message}{self.RESET}"
        )


def compose(*functions: Callable[[Any], Any]) -> Callable[[Any], Any]:
    """
    Composes single-argument functions from right to left.
    """
    return reduce(lambda f, g: lambda x: f(g(x)), functions)
