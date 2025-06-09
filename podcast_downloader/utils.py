import logging
import re
from functools import reduce
from typing import Callable, Any, List, Tuple

class ConsoleOutputFormatter(logging.Formatter):
    """
    An advanced logging formatter that uses special cases and regex patterns
    to apply Catppuccin Mocha colors to log messages.
    """

    RESET = "\033[0m"

    # --- Catppuccin Mocha Palette ---
    RED = "\033[38;2;243;139;168m"
    GREEN = "\033[38;2;166;227;161m"
    YELLOW = "\033[38;2;249;226;175m"
    BLUE = "\033[38;2;137;180;250m"
    CYAN = "\033[38;2;148;226;213m"
    WHITE = "\033[38;2;186;194;222m"
    BRIGHT_BLACK = "\033[38;2;88;91;112m"
    ROSEWATER = "\033[38;2;245;224;220m"
    FLAMINGO = "\033[38;2;242;205;205m"
    MAUVE = "\033[38;2;203;166;247m"
    LAVENDER = "\033[38;2;180;190;254m"
    MAROON = "\033[38;2;235;160;172m"
    SKY = "\033[38;2;137;220;235m"
    OVERLAY2 = "\033[38;2;147;153;178m"
    PINK = "\033[38;2;245;194;231m"

    LEVEL_COLORS = {
        logging.DEBUG: BRIGHT_BLACK,
        logging.INFO: BLUE,
        logging.WARNING: YELLOW,
        logging.ERROR: RED,
    }

    KEYWORD_RULES: List[Tuple[str, str]] = [
        (r'\b(Checking)\b', BLUE),
        (r'\b(Last downloaded file:)\b', BLUE),
        (r'(".*?")', ROSEWATER),
        (r'\b(Finished\.)', GREEN),
        (r'\b(Nothing new to download\.)', MAUVE),
    ]

    def __init__(self) -> None:
        super().__init__(fmt="", datefmt="%Y-%m-%d %H:%M:%S", style="%")

    def format(self, record: logging.LogRecord) -> str:
        timestamp = self.formatTime(record, self.datefmt)
        message = self._format_message(record)
        prefix = f"{self.OVERLAY2}[{self.RESET}{self.FLAMINGO}{timestamp}{self.RESET}{self.OVERLAY2}]{self.RESET} "
        return prefix + message

    def _format_message(self, record: logging.LogRecord) -> str:
        message = self.formatMessage(record)

        if record.msg.startswith("Loading configuration from file:"):
            return re.sub(
                r'(Loading configuration from file: )(".*?")',
                lambda m: f"{self.CYAN}{m.group(1)}{self.RESET}{self.WHITE}{m.group(2)}{self.RESET}",
                message
            )

        elif record.msg.startswith('{}: Downloading new episode...') and record.args:
            podcast_name = record.args[0]
            text_part = record.msg.replace('{}', f'"{podcast_name}"')
            return f"{self.CYAN}Downloading new episode of: {self.RESET}{self.ROSEWATER}{text_part}{self.RESET}"

        elif record.msg.strip().startswith("-> Source URL:") and record.args:
            return f"    {self.LAVENDER}-> Source URL:{self.RESET} {self.SKY}\"{record.args[0]}\"{self.RESET}"

        elif record.msg.strip().startswith("-> Saved as:") and record.args:
            return f"    {self.LAVENDER}-> Saved as:{self.RESET} {self.MAROON}\"{record.args[0]}\"{self.RESET}"

        color = self.LEVEL_COLORS.get(record.levelno, self.BLUE)
        colored = f"{color}{message}{self.RESET}"

        for pattern, keyword_color in self.KEYWORD_RULES:
            colored = re.sub(pattern, lambda m: f"{keyword_color}{m.group(1)}{color}", colored)

        if record.exc_info:
            colored += "\n" + self.formatException(record.exc_info)

        return colored


def compose(*functions: Callable[[Any], Any]) -> Callable[[Any], Any]:
    """
    Composes single-argument functions from right to left:
    compose(f, g, h)(x) == f(g(h(x)))
    """
    if not functions:
        raise ValueError("At least one function must be provided.")
    return reduce(lambda f, g: lambda x: f(g(x)), functions)
