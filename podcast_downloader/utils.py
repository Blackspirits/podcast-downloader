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
        """
        Initializes the formatter.
        
        The key to fixing the ValueError is to pass a `fmt` string to the parent
        constructor that includes `%(asctime)s`. This ensures the base formatter's
        `usesTime()` method returns True, which correctly sets up the internal
        time-handling machinery. Our custom `format()` method below will still
        override the final output, but this step is crucial for initialization.
        """
        super().__init__(
            fmt="%(asctime)s | %(message)s",  # This `fmt` enables the time machinery.
            datefmt="%Y-%m-%d %H:%M:%S"       # This is the date format we will use.
        )

    def format(self, record: LogRecord) -> str:
        """
        Formats the log record with appropriate colors, overriding the default.
        """
        # 1. Get the color for the specific log level.
        level_color = self.COLORS.get(record.levelno, self.RESET)

        # 2. Format the timestamp using the parent class's logic and our datefmt.
        timestamp = self.formatTime(record, self.datefmt)

        # 3. Get the final formatted log message from the record.
        message = record.getMessage()
        
        # 4. Append exception information if it exists.
        if record.exc_info:
            message += "\n" + self.formatException(record.exc_info)

        # 5. Manually construct the final colored string with our desired layout.
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
