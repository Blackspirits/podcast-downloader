from functools import reduce
from logging import Formatter, DEBUG, INFO, WARNING, ERROR

class ConsoleOutputFormatter(Formatter):
    COLORS = {
        DEBUG: "\033[38;5;245m",    # Overlay2
        INFO: "\033[38;5;67m",      # Sapphire
        WARNING: "\033[38;5;215m",  # Peach
        ERROR: "\033[38;5;168m",    # Maroon
    }

    def __init__(self) -> None:
        # Applies color to the date as well (soft gray)
        date_color = "\033[2m"
        reset = "\033[0m"
        fmt = f"[{date_color}%(asctime)s{reset}] %(message)s"
        super().__init__(fmt, "%Y-%m-%d %H:%M:%S")

    def format(self, record):
        # Use standard formatting to apply args
        formatted_message = super().format(record)
        color = self.COLORS.get(record.levelno, "")
        reset = "\033[0m"

        # Applies color only to the message (keeps the date gray)
        return f"{color}{formatted_message}{reset}"

def compose(*functions):
    return reduce(lambda f, g: lambda x: f(g(x)), functions)
