from functools import reduce
from logging import Formatter, LogRecord, DEBUG, INFO, WARNING, ERROR
from typing import Callable, Any

class ConsoleOutputFormatter(Formatter):
    """
    A custom logging formatter that adds color to terminal output.
    
    It formats messages with a gray timestamp and a message colored
    according to the log level (e.g., blue for INFO, yellow for WARNING).
    """

    # ANSI escape codes for colors
    DATE_COLOR = "\033[2m"  # Dim gray
    RESET = "\033[0m"

    COLORS = {
        DEBUG: "\033[38;5;245m",    # Overlay2 (grayish)
        INFO: "\033[38;5;67m",       # Sapphire (blue)
        WARNING: "\033[38;5;215m",   # Peach (yellow/orange)
        ERROR: "\033[38;5;168m",     # Maroon (red)
    }

    def __init__(self) -> None:
        """Initializes the formatter."""
        # It's crucial to pass a format string containing `%(asctime)s` to the
        # parent constructor. This ensures the formatter's `usesTime()` method
        # returns True, which correctly sets up the internal time-handling
        # machinery and prevents the ValueError. We override the final output
        # in our custom `format()` method, so this `fmt` is not directly used.
        super().__init__(
            fmt="%(asctime)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

    def format(self, record: LogRecord) -> str:
        """
        Formats the log record with appropriate colors.
        """
        # 1. Get the color for the specific log level.
        level_color = self.COLORS.get(record.levelno, self.RESET)

        # 2. Format the timestamp using the parent class's logic.
        timestamp = self.formatTime(record, self.datefmt)

        # 3. Get the formatted log message itself.
        message = record.getMessage()
        
        # 4. Handle exceptions if they exist.
        if record.exc_info:
            message += "\n" + self.formatException(record.exc_info)

        # 5. Manually construct the final colored string.
        return (
            f"[{self.DATE_COLOR}{timestamp}{self.RESET}] "
            f"{level_color}{message}{self.RESET}"
        )


def compose(*functions: Callable[[Any], Any]) -> Callable[[Any], Any]:
    """
    Composes single-argument functions from right to left.

    For example, `compose(f, g, h)` is equivalent to `lambda x: f(g(h(x)))`.
    """
    return reduce(lambda f, g: lambda x: f(g(x)), functions)
