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
        
        elif message.startswith("    -> Source URL:"): # Usamos `record.msg` para a correspondência exata do prefixo
            url = record.args[0] if record.args else "?"
            # Constrói a string com cores específicas, com RESET após cada parte para evitar vazamento
            formatted_message_content = (
                f"{self.LAVENDER}    -> Source URL: {self.RESET}" # Cor LAVENDER para o texto fixo, seguido de RESET
                f"{self.SKY}\"{url}\"{self.RESET}"                 # Cor SKY para a URL, seguido de RESET
            )
        
        elif message.startswith('    -> Saved as:'): # Usamos `record.msg` para a correspondência exata do prefixo
            filename = record.args[0] if record.args else "?"
            # Constrói a string com cores específicas, com RESET após cada parte para evitar vazamento
            formatted_message_content = (
                f"{self.LAVENDER}    -> Saved as:    {self.RESET}" # Cor LAVENDER para o texto fixo, seguido de RESET
                f"{self.SAPPHIRE}\"{filename}\"{self.RESET}"       # Cor SAPPHIRE para o nome do ficheiro, seguido de RESET
            )
        
        elif message.startswith('Last downloaded file:'):
            filename = record.args[0] if record.args else "?"
            # Constrói a string com cores específicas
            formatted_message_content = (
                f"{self.BLUE}Last downloaded file: {self.RESET}" # Cor BLUE para o texto fixo, seguido de RESET
                f"{self.SAPPHIRE}\"{filename}\"{self.RESET}"     # Cor SAPPHIRE para o nome do ficheiro, seguido de RESET
            )
 
        else: # Este é o bloco para mensagens genéricas que não foram capturadas acima
            default_color = self.LEVEL_COLORS.get(record.levelno, self.BLUE)
            
            # Aplica a cor do nível a toda a mensagem primeiro
            formatted_message_content = f"{default_color}{message}{self.RESET}"

            # Agora, aplica as regras de palavras-chave sobre a mensagem JÁ colorida
            # É crucial que as regras sejam específicas e que o RESET seja aplicado corretamente
            for pattern, color in self.KEYWORD_RULES:
                try:
                    formatted_message_content = re.sub(
                        pattern,
                        # Para garantir que a cor default_color é restaurada APÓS a palavra-chave
                        lambda m: f"{color}{m.group(0)}{self.RESET}{default_color}",
                        formatted_message_content
                    )
                except re.error as e:
                    print(f"[Formatter] Padrão inválido de REGEX ignorado: {pattern} ({e})")
        
        # Adiciona informações de exceção (tracebacks) se existirem
        if record.exc_info:
            # Garante que a formatação do traceback também é limpa e tem a cor correta
            formatted_message_content += "\n" + self.formatException(record.exc_info)
            # Tracebacks são geralmente vermelhos ou um tom mais escuro
            # Pode querer aplicar uma cor específica aqui se não for o padrão do logging.
            
        # Divide a mensagem final em linhas e adiciona o timestamp e a cor final
        lines = formatted_message_content.splitlines()
        colored_lines = []
        for i, line in enumerate(lines):
            stripped_line = line.strip()
            if stripped_line != "": # Ignora linhas vazias que podem ter sido geradas
                # Esta é a camada final de coloração, que adiciona o timestamp
                # O importante é que a cor do 'line' (já formatada) não seja anulada pelo RESET do timestamp.
                # O {self.RESET} final após o timestamp garante que a linha do log em si está na cor certa.
                colored_lines.append(
                    f"{self.MAROON}[{self.RESET}{self.PEACH}{timestamp}{self.RESET}{self.MAROON}]{self.RESET} {line}"
                )
            elif i > 0 and lines[i-1].strip() != "":
                # Adiciona uma linha vazia para espaçamento se a linha anterior não era vazia
                colored_lines.append("")

        # Junta as linhas com quebras de linha e retorna
        return "\n".join(colored_lines)

def compose(*functions: Callable[[Any], Any]) -> Callable[[Any], Any]:
    """Composes single-argument functions from right to left."""
    return reduce(lambda f, g: lambda x: f(g(x)), functions)
