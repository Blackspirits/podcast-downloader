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
        """Initializes the formatter, setting only the date format."""
        # The base Formatter is initialized without a message format string,
        # as we are constructing it manually in the format() method.
        super().__init__(fmt=None, datefmt="%Y-%m-%d %H:%M:%S")

    def format(self, record: LogRecord) -> str:
        """
        Formats the log record with appropriate colors.

        This method fixes a bug in the original implementation by ensuring
        the message color does not override the timestamp color.
        """
        # 1. Get the color for the specific log level. Default to RESET if not found.
        level_color = self.COLORS.get(record.levelno, self.RESET)

        # 2. Format the timestamp using the parent class's logic.
        timestamp = self.formatTime(record, self.datefmt)

        # 3. Get the formatted log message itself.
        message = record.getMessage()
        
        # 4. Handle exceptions if they exist.
        if record.exc_info:
            # formatException returns a multi-line string.
            # We add it on a new line after the original message.
            message += "\n" + self.formatException(record.exc_info)

        # 5. Manually construct the final colored string.
        #    - Timestamp is always gray.
        #    - Message is colored by level.
        return (
            f"[{self.DATE_COLOR}{timestamp}{self.RESET}] "
            f"{level_color}{message}{self.RESET}"
        )


def compose(*functions: Callable[[Any], Any]) -> Callable[[Any], Any]:
    """
    Composes single-argument functions from right to left.

    For example, `compose(f, g, h)` is equivalent to `lambda x: f(g(h(x)))`.

    Args:
        *functions: A sequence of single-argument functions to compose.

    Returns:
        A new function that represents the composition of the input functions.
    
    Example:
        add_one = lambda x: x + 1
        double = lambda x: x * 2
        
        add_one_then_double = compose(double, add_one)
        # Result is 6, because it calculates double(add_one(2))
        result = add_one_then_double(2)
    """
    return reduce(lambda f, g: lambda x: f(g(x)), functions)
