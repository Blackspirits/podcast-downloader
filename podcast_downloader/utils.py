# (With Catppuccin Mocha Theme)

import logging
import re
from functools import reduce
from typing import Callable, Any, List, Tuple

class ConsoleOutputFormatter(logging.Formatter):
    """
    An advanced logging formatter that uses regular expressions and special cases
    to apply Catppuccin Mocha colors to log messages.
    """
    # Using TrueColor (24-bit) codes for maximum color fidelity
    RESET = "\033[0m"

    # --- Catppuccin Mocha Palette ---
    RED = "\033[38;2;243;139;168m"      # Error
    GREEN = "\033[38;2;166;227;161m"    # Success
    YELLOW = "\033[38;2;249;226;175m"  # Warning
    BLUE = "\033[38;2;137;180;250m"     # Default INFO
    CYAN = "\033[38;2;148;226;213m"     # Actions
    WHITE = "\033[38;2;186;194;222m"    # Timestamp text
    BRIGHT_BLACK = "\033[38;2;88;91;112m" # DEBUG text & Timestamp brackets
    ROSEWATER = "\033[38;2;245;224;220m" # Quoted Filenames
    FLAMINGO = "\033[38;2;242;205;205m" # Config Path
    MAUVE = "\033[38;2;203;166;247m"    # 'Nothing new' message
    LAVENDER = "\033[38;2;180;190;254m" # "saved as" text
    MAROON = "\033[38;2;235;160;172m"
    SKY = "\033[38;2;137;220;235m"      # Links/URLs
    PINK = "\033[38;2;245;194;231m"
    BASE = "\033[38;2;30;30;46m"         # Background
    TEXT = "\033[38;2;205;214;244m"       # Foreground text
    SURFACE0 = "\033[38;2;49;50;68m"     # A darker surface color
    SURFACE1 = "\033[38;2;69;71;90m"     # Another darker surface color
    SURFACE2 = "\033[38;2;88;91;112m"    # Similar to your BRIGHT_BLACK, but typically distinct in palette
    OVERLAY0 = "\033[38;2;108;112;134m"
    OVERLAY1 = "\033[38;2;127;132;156m"
    OVERLAY2 = "\033[38;2;147;153;178m"
    PEACH = "\033[38;2;255;180;128m"
    SAPPHIRE = "\033[38;2;116;199;236m"
    TEAL = "\033[38;2;152;211;190m" 

    # Dictionary mapping log levels to color constants
    LEVEL_COLORS = {
        logging.DEBUG: BRIGHT_BLACK,
        logging.INFO: BLUE,
        logging.WARNING: YELLOW,
        logging.ERROR: RED,
    }

    # General rules for simple log messages
    KEYWORD_RULES: List[Tuple[str, str]] = [
        (r'(Checking)', BLUE),
        (r'(Last downloaded file:)', BLUE),
        (r'(Loading configuration from file:)', BLUE),
        (r'(".*?")', ROSEWATER),
        (r'(Finished\.)', GREEN),
        (r'(Nothing new for:)', BLUE),
        (r'(-> Source URL:)', MAUVE),
        (r'(-> Saved as:)', MAUVE),
        (r'(Downloading new episode of:)', BLUE),
       
    ]

    def __init__(self) -> None:
        """Initializes the formatter."""
        super().__init__(fmt="{message}", datefmt="%Y-%m-%d %H:%M:%S", style='{')

    def format(self, record: logging.LogRecord) -> str:
        timestamp = self.formatTime(record, self.datefmt)
        message = record.getMessage()

        # Handle the "Loading configuration" line as a special case
        if record.msg.startswith('Loading configuration from file:'):
            pattern = r'(Loading configuration from file: )(".*?")'
            formatted_message = re.sub(
                pattern,
                lambda m: f"{self.BLUE}{m.group(1)}{self.PINK}{m.group(2)}{self.RESET}",
                message
            )

        elif message.startswith('Downloading new episode of:'):
            podcast_name = record.args[0] if record.args else "?"
            formatted_message = (
                "\n"
                f"{self.BLUE}Downloading new episode of: {self.GREEN}\"{podcast_name}\"{self.RESET}"
            )

        elif message.startswith('Nothing new for:'):
            podcast_name = record.args[0] if record.args else "?"
            formatted_message = (
                "\n"
                f"{self.BLUE}Nothing new for: {self.GREEN}\"{podcast_name}\"{self.RESET}"
            )
    
        elif message.startswith("    -> Source URL:"):
            url = record.args[0] if record.args else "?"
            formatted_message = (
                "\n"
                f"{self.MAUVE}    -> Source URL: {self.RESET}{self.SKY}\"{url}\"{self.RESET}"
            )
    
        elif message.startswith('    -> Saved as:  '):
            filename = record.args[0] if record.args else "?"
            formatted_message = (
                "\n"
                f"{self.MAUVE}    -> Saved as:  {self.RESET}{self.SAPPHIRE}\"{filename}\"{self.RESET}"
            )
    
        elif message.startswith('Last downloaded file:'):
            filename = record.args[0] if record.args else "?"
            formatted_message = f"{self.BLUE}Last downloaded file: {self.SAPPHIRE}\"{filename}\"{self.RESET}"
    
        else:
            default_color = self.LEVEL_COLORS.get(record.levelno, self.BLUE)
            formatted_message = (
                "\n"
                f"{default_color}{message}{self.RESET}"
            )
    
            for pattern, color in self.KEYWORD_RULES:
                try:
                    formatted_message = re.sub(
                        pattern,
                        lambda m: f"{color}{m.group(1)}{default_color}",
                        formatted_message
                    )
                except re.error as e:
                    print(f"[Formatter] Padrão inválido ignorado: {pattern} ({e})")
    
        if record.exc_info:
            formatted_message += "\n" + self.formatException(record.exc_info)
    
        lines = formatted_message.splitlines()
        colored_lines = [
            f"{self.MAROON}[{self.RESET}{self.PEACH}{timestamp}{self.RESET}{self.MAROON}]{self.RESET} {line}"
            for line in lines if line.strip() != ""
        ]
        return "\n".join(colored_lines)


def compose(*functions: Callable[[Any], Any]) -> Callable[[Any], Any]:
    """Composes single-argument functions from right to left."""
    return reduce(lambda f, g: lambda x: f(g(x)), functions)
