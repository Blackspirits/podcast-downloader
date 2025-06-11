import os
import logging
import re
from functools import reduce
from typing import Callable, Any, List, Tuple

class ConsoleOutputFormatter(logging.Formatter):
    """
    An advanced logging formatter that uses regular expressions and special cases
    to apply Catppuccin Mocha colors to log messages.
    """
    RESET = "\033[0m"

    # --- Catppuccin Mocha Palette ---
    RED = "\033[38;2;243;139;168m"      # Error
    GREEN = "\033[38;2;166;227;161m"    # Success
    YELLOW = "\033[38;2;249;226;175m"  # Warning
    BLUE = "\033[38;2;137;180;250m"      # Default INFO
    CYAN = "\033[38;2;148;226;213m"      # Actions
    WHITE = "\033[38;2;186;194;222m"    # Timestamp text
    BRIGHT_BLACK = "\033[38;2;88;91;112m" # DEBUG text & Timestamp brackets
    ROSEWATER = "\033[38;2;245;224;220m" # Quoted Filenames
    FLAMINGO = "\033[38;2;242;205;205m" # Config Path
    MAUVE = "\033[38;2;203;166;247m"    # 'Nothing new' message
    LAVENDER = "\033[38;2;180;190;254m" # "saved as" text
    MAROON = "\033[38;2;235;160;172m"
    SKY = "\033[38;2;137;220;235m"      # Links/URLs
    PINK = "\033[38;2;245;194;231m"
    BASE = "\033[38;2;30;30;46m"        # Background
    TEXT = "\033[38;2;205;214;244m"        # Foreground text
    SAPPHIRE = "\033[38;2;116;199;236m"
    PEACH = "\033[38;2;255;180;128m" # Certifique-se que esta está definida

    # Dictionary mapping log levels to color constants
    LEVEL_COLORS = {
        logging.DEBUG: BRIGHT_BLACK,
        logging.INFO: BLUE,
        logging.WARNING: YELLOW,
        logging.ERROR: RED,
        logging.CRITICAL: RED,
    }

    # General rules for simple log messages
    # Estas regras são aplicadas APENAS no bloco 'else', para mensagens genéricas.
    # Elas NÃO são para mensagens que já são tratadas pelos 'elif' específicos.
    KEYWORD_RULES: List[Tuple[str, str]] = [
        (r'(".*?")', ROSEWATER), # Aspas genéricas
        (r'(Finished\.)', GREEN),
        (r'(Nothing new for:)', BLUE), # Mantido, mas o elif é mais específico.
        # Adicione mais regras genéricas se necessário
        (r'(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})', WHITE), # Exemplo: colorir timestamps genéricos
    ]

    def __init__(self) -> None:
        """Initializes the formatter."""
        super().__init__(fmt="{message}", datefmt="%Y-%m-%d %H:%M:%S", style='{')

    def format(self, record: logging.LogRecord) -> str:
        timestamp = self.formatTime(record, self.datefmt)
        message = record.getMessage() # Esta é a mensagem original sem cores

        # Por padrão, assume que a mensagem será formatada com a cor do nível
        formatted_message_content = "" # Inicializa para garantir que é sempre definida

        # --- Tratamento de casos especiais com cores personalizadas ---
        # A ordem importa aqui: as condições mais específicas primeiro.
        # Removemos o '\n' inicial nas f-strings aqui, pois ele é adicionado no final por linha.

        if record.msg.startswith('Loading configuration from file:'):
            pattern = r'(Loading configuration from file: )(".*?")'
            formatted_message_content = re.sub(
                pattern,
                lambda m: f"{self.BLUE}{m.group(1)}{self.FLAMINGO}{m.group(2)}{self.RESET}",
                message
            )

        elif message.startswith('Downloading new episode of:'):
            podcast_name = record.args[0] if record.args else "?"
            formatted_message_content = f"{self.BLUE}Downloading new episode of: {self.GREEN}\"{podcast_name}\"{self.RESET}"

        elif message.startswith('Nothing new for:'):
            podcast_name = record.args[0] if record.args else "?"
            formatted_message_content = f"{self.BLUE}Nothing new for: {self.MAUVE}\"{podcast_name}\"{self.RESET}"

        elif message.startswith('Checking'):
            podcast_name = record.args[0] if record.args else "?"
            formatted_message_content = f"{self.BLUE}Checking {self.GREEN}\"{podcast_name}\"{self.RESET}"
        
        elif message.startswith("    -> Source URL:"):
            url = record.args[0] if record.args else "?"
            # REMOVIDO os self.RESET intermédios.
            # A cor LAVENDER começa, depois a cor SKY, e só o RESET final fecha tudo.
            formatted_message_content = (
                f"{self.LAVENDER}    -> Source URL: " # Texto inicial LAVENDER
                f"{self.SKY}\"{url}\"{self.RESET}"    # URL SKY, e o RESET final para toda a linha
            )
        
        elif message.startswith('    -> Saved as:'):
            filename = record.args[0] if record.args else "?"
            # REMOVIDO os self.RESET intermédios.
            # A cor LAVENDER começa, depois a cor SAPPHIRE, e só o RESET final fecha tudo.
            formatted_message_content = (
                f"{self.LAVENDER}    -> Saved as:    " # Texto inicial LAVENDER
                f"{self.SAPPHIRE}\"{filename}\"{self.RESET}" # Nome do ficheiro SAPPHIRE, e o RESET final para toda a linha
            )
        
        elif message.startswith('Last downloaded file:'):
            filename = record.args[0] if record.args else "?"
            # REMOVIDO o self.RESET intermédio.
            # A cor BLUE começa, depois SAPPHIRE, e só o RESET final fecha tudo.
            formatted_message_content = (
                f"{self.BLUE}Last downloaded file: " # Texto inicial BLUE
                f"{self.SAPPHIRE}\"{filename}\"{self.RESET}" # Nome do ficheiro SAPPHIRE, e o RESET final para toda a linha
            )
 
        else: # Este é o bloco para mensagens genéricas que não foram capturadas acima
            default_color = self.LEVEL_COLORS.get(record.levelno, self.BLUE)
            
            formatted_message_content = f"{default_color}{message}" # A cor default começa, SEM RESET AQUI

            for pattern, color in self.KEYWORD_RULES:
                try:
                    # m.group(0) é a correspondência inteira do padrão.
                    # {self.RESET} fecha a cor anterior. {default_color} reabre a cor do nível.
                    formatted_message_content = re.sub(
                        pattern,
                        # Aplica a cor específica e volta para a cor default da linha
                        lambda m: f"{color}{m.group(0)}{self.RESET}{default_color}",
                        formatted_message_content
                    )
                except re.error as e:
                    print(f"[Formatter] Padrão inválido de REGEX ignorado: {pattern} ({e})")
            
            formatted_message_content = f"{formatted_message_content}{self.RESET}" # Adiciona o RESET FINAL aqui para o bloco else

        # Adiciona informações de exceção (tracebacks) se existirem
        if record.exc_info:
            formatted_message_content += "\n" + self.formatException(record.exc_info)
            
        # Divide a mensagem final em linhas e adiciona o timestamp e cor final a cada uma
        lines = formatted_message_content.splitlines()
        colored_lines = []
        for i, line in enumerate(lines):
            stripped_line = line.strip()
            if stripped_line != "":
                # A cor já vem na 'line'. O último {self.RESET} é para fechar o timestamp
                colored_lines.append(
                    f"{self.MAROON}[{self.RESET}{self.PEACH}{timestamp}{self.RESET}{self.MAROON}]{self.RESET} {line}"
                )
            elif i > 0 and lines[i-1].strip() != "":
                colored_lines.append("")

        return "\n".join(colored_lines)

def compose(*functions: Callable[[Any], Any]) -> Callable[[Any], Any]:
    """Composes single-argument functions from right to left."""
    return reduce(lambda f, g: lambda x: f(g(x)), functions)
