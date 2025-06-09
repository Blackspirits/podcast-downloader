from functools import reduce
from logging import Formatter, LogRecord, DEBUG, INFO, WARNING, ERROR
from typing import Callable, Any

class ConsoleOutputFormatter(Formatter):
    """
    A custom logging formatter that adds color to terminal output.
    """
    DATE_COLOR = "\033[2m"
    RESET = "\033[0m"
    COLORS = {
        DEBUG: "\033[38;5;245m",
        INFO: "\033[38;5;67m",
        WARNING: "\033[38;5;215m",
        ERROR: "\033[38;5;168m",
    }

    def __init__(self) -> None:
        """
        Initializes the formatter using modern '{'-style formatting.
        This completely avoids the ambiguity of the '%' character that was
        causing the ValueError.
        """
        super().__init__(
            fmt="{message}",  # Use a simple {}-style placeholder
            datefmt="%Y-%m-%d %H:%M:%S",
            style='{'  # Explicitly set the style to '{'
        )

    def format(self, record: LogRecord) -> str:
        """
        Formats the log record with appropriate colors.
        """
        level_color = self.COLORS.get(record.levelno, self.RESET)
        timestamp = self.formatTime(record, self.datefmt)
        
        message = record.getMessage()

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
