from functools import reduce
from logging import Formatter, DEBUG, INFO, WARNING, ERROR, CRITICAL

class ConsoleOutputFormatter(Formatter):
    COLORS = {
        DEBUG: "\033[94mDebug:\033[0m",         # sky
        INFO: "\033[38;5;110mInfo:\033[0m",     # blue (approximation Catppuccin 'blue')
        WARNING: "\033[33mWarning:\033[0m",     # yellow
        ERROR: "\033[31mError:\033[0m",         # red
        CRITICAL: "\033[91mCritical:\033[0m",   # more intense red
    }

    def __init__(self) -> None:
        # Timestamp in gray (dim), message blank by default
        super().__init__("[\033[2m%(asctime)s\033[0m] %(message)s", "%Y-%m-%d %H:%M:%S")

    def format(self, record):
        # Highlight arguments (such as files, numbers) with light white
        if record.args:
            record.msg = record.msg.replace("%s", "\033[97m%s\033[0m").replace(
                "%d", "\033[97m%d\033[0m"
            )

        # Level prefix with ANSI color
        if record.levelno in self.COLORS:
            record.msg = f"{self.COLORS[record.levelno]} {record.msg}"

        return super().format(record)


def compose(*functions):
    return reduce(lambda f, g: lambda x: f(g(x)), functions)
