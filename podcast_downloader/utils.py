import os
import logging
import re
from functools import reduce
from typing import Callable, Any, List, Tuple
# from logging.handlers import TimedRotatingFileHandler # Removido para este ficheiro

class ConsoleOutputFormatter(logging.Formatter):
    """
    An advanced logging formatter that uses regular expressions and special cases
    to apply Catppuccin Mocha colors to log messages.
    """
    # ... (Seus códigos de cor Catppuccin Mocha) ...
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
    SURFACE0 = "\033[38;2;49;50;68m"      # A darker surface color
    SURFACE1 = "\033[38;2;69;71;90m"      # Another darker surface color
    SURFACE2 = "\033[38;2;88;91;112m"     # Similar to your BRIGHT_BLACK, but typically distinct in palette
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
        logging.CRITICAL: RED,
    }

    # General rules for simple log messages
    KEYWORD_RULES: List[Tuple[str, str]] = [
        # Padrões que podem ser aplicados em mensagens genéricas
        # Note que se estes patterns corresponderem a uma mensagem já tratada por um elif acima,
        # este loop não será executado para essa mensagem.
        (r'(Last downloaded file:)', BLUE), # Já tem um elif, mas se estiver aqui, ele é genérico.
        (r'(Loading configuration from file:)', BLUE), # Já tem um elif
        (r'(".*?")', ROSEWATER), # Aspas genéricas
        (r'(Finished\.)', GREEN),
        (r'(Nothing new for:)', BLUE),
        (r'(-> Source URL: )(".*?")', LAVENDER), # Também tem elif, mas aqui para genérico.
        (r'(-> Saved as: )(".*?")', LAVENDER), # Também tem elif, mas aqui para genérico.
        (r'(Downloading new episode of:)', BLUE), # Também tem elif, mas aqui para genérico.
        (r'(Checking)', BLUE), # Também tem elif, mas aqui para genérico.
        # Adicione mais regras genéricas se necessário, por exemplo, para timestamps dentro de mensagens
        (r'(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})', WHITE), # Exemplo: colorir timestamps genéricos
    ]

    def __init__(self) -> None:
        """Initializes the formatter."""
        # Use o estilo '{' e o fmt com o placeholder {message}
        super().__init__(fmt="{message}", datefmt="%Y-%m-%d %H:%M:%S", style='{')

    def format(self, record: logging.LogRecord) -> str:
        timestamp = self.formatTime(record, self.datefmt)
        message = record.getMessage() # Esta é a mensagem original sem cores

        # Por padrão, assume que a mensagem será formatada com a cor do nível
        formatted_message = "" # Inicializa para evitar NameError

        # --- Tratamento de casos especiais com cores personalizadas ---
        # Estes blocos elif devem ser os primeiros a serem verificados
        if record.msg.startswith('Loading configuration from file:'):
            pattern = r'(Loading configuration from file: )(".*?")'
            formatted_message = re.sub(
                pattern,
                lambda m: f"{self.BLUE}{m.group(1)}{self.FLAMINGO}{m.group(2)}{self.RESET}", # Use FLAMINGO para o caminho do config
                message # Aplica o regex na mensagem original
            )

        elif message.startswith('Downloading new episode of:'):
            podcast_name = record.args[0] if record.args else "?"
            formatted_message = (
                f"\n{self.BLUE}Downloading new episode of: {self.GREEN}\"{podcast_name}\"{self.RESET}"
            )

        elif message.startswith('Nothing new for:'):
            podcast_name = record.args[0] if record.args else "?"
            formatted_message = (
                f"\n{self.BLUE}Nothing new for: {self.MAUVE}\"{podcast_name}\"{self.RESET}" # Use MAUVE para 'Nothing new'
            )

        elif message.startswith('Checking'):
            podcast_name = record.args[0] if record.args else "?"
            formatted_message = (
                f"\n{self.BLUE}Checking {self.GREEN}\"{podcast_name}\"{self.RESET}"
            )
        
        elif message.startswith("    -> Source URL:"):
            url = record.args[0] if record.args else "?"
            # Corrigido: Garante que o LAVENDER fecha antes de SKY, e SKY fecha antes de RESET final da linha.
            formatted_message = (
                f"\n{self.LAVENDER}    -> Source URL: {self.RESET}" # Texto inicial LAVENDER e RESET
                f"{self.SKY}\"{url}\"{self.RESET}"                  # URL SKY e RESET
            )
        
        elif message.startswith('    -> Saved as:'):
            filename = record.args[0] if record.args else "?"
            # Corrigido: Garante que o LAVENDER fecha antes de SAPPHIRE, e SAPPHIRE fecha antes de RESET final da linha.
            formatted_message = (
                f"\n{self.LAVENDER}    -> Saved as:    {self.RESET}" # Texto inicial LAVENDER e RESET
                f"{self.SAPPHIRE}\"{filename}\"{self.RESET}"         # Nome do ficheiro SAPPHIRE e RESET
            )
        
        elif message.startswith('Last downloaded file:'):
            filename = record.args[0] if record.args else "?"
            # Corrigido: Similarmente, garanta que a cor da parte "Last downloaded file:" fecha.
            formatted_message = (
                f"{self.BLUE}Last downloaded file: {self.RESET}" # Texto inicial BLUE e RESET
                f"{self.SAPPHIRE}\"{filename}\"{self.RESET}"     # Nome do ficheiro SAPPHIRE e RESET
            )
 
        else: # Este é o bloco para mensagens genéricas que não foram capturadas acima
            default_color = self.LEVEL_COLORS.get(record.levelno, self.BLUE)
            
            # Aplica a cor do nível a toda a mensagem primeiro
            formatted_message = f"{default_color}{message}{self.RESET}" # Começa com a cor padrão do nível

            # Agora, aplica as regras de palavras-chave sobre a mensagem JÁ colorida
            # É crucial que as regras sejam específicas e que o RESET seja aplicado corretamente
            for pattern, color in self.KEYWORD_RULES:
                try:
                    # m.group(0) é a correspondência inteira do padrão.
                    # {self.RESET} fecha a cor anterior. {default_color} reabre a cor do nível.
                    formatted_message = re.sub(
                        pattern,
                        lambda m: f"{color}{m.group(0)}{self.RESET}{default_color}",
                        formatted_message
                    )
                except re.error as e:
                    # Em caso de erro no padrão regex, apenas imprime um aviso na consola
                    # sem parar o formatador.
                    print(f"[Formatter] Padrão inválido de REGEX ignorado: {pattern} ({e})")
        
        # Adiciona informações de exceção (tracebacks) se existirem
        if record.exc_info:
            formatted_message += "\n" + self.formatException(record.exc_info)
        
        # Divide a mensagem em linhas e adiciona o timestamp e cor final a cada uma
        lines = formatted_message.splitlines()
        colored_lines = [
            f"{self.MAROON}[{self.RESET}{self.PEACH}{timestamp}{self.RESET}{self.MAROON}]{self.RESET} {line.strip()}" # strip() para remover espaços extra
            for line in lines if line.strip() != "" # Ignora linhas vazias
        ]
        
        # Junta as linhas com quebras de linha e retorna
        return "\n".join(colored_lines)

# Removida: Toda a configuração de logging (logging.getLogger(), handlers, etc.).
# Isto será feito APENAS no __main__.py.

def compose(*functions: Callable[[Any], Any]) -> Callable[[Any], Any]:
    """Composes single-argument functions from right to left."""
    return reduce(lambda f, g: lambda x: f(g(x)), functions)
