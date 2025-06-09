import logging
from functools import reduce
from typing import Callable, Any

class ConsoleOutputFormatter(logging.Formatter):
    """
    A custom logging formatter that adds color to terminal output.
    """
    DATE_COLOR = "\033[2m"
    RESET = "\033[0m"
    COLORS = {
        logging.DEBUG: "\033[38;5;245m",
        logging.INFO: "\033[38;5;67m",
        logging.WARNING: "\033[38;5;215m",
        logging.ERROR: "\033[38;5;168m",
    }

    def __init__(self) -> None:
        """
        Initializes the formatter using modern '{'-style formatting.
        """
        super().__init__(
            fmt="{message}",
            datefmt="%Y-%m-%d %H:%M:%S",
            style='{'
        )

    def format(self, record: logging.LogRecord) -> str:
        """
        Formats the log record with appropriate colors.
        """
        level_color = self.COLORS.get(record.levelno, self.RESET)
        timestamp = self.formatTime(record, self.datefmt)

        # --- THIS IS THE FINAL FIX ---
        # Instead of calling record.getMessage(), which uses old %-style formatting,
        # we format the message ourselves using the modern {}-style.
        if record.args:
            message = record.msg.format(*record.args)
        else:
            message = record.msg
        # --- END OF FIX ---

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
