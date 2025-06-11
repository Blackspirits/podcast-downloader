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
    SAPPHIRE = "\033[38;2;116;199;236m" # Mantido
    TEAL = "\033[38;2;152;211;190m"     # Mantido
    
    # Removido: SURFACE0, SURFACE1, SURFACE2, OVERLAY0, OVERLAY1, OVERLAY2, PEACH.
    # Se precisar de alguma destas cores, adicione-as novamente.
    # PEACH foi mantido na formatação do timestamp.

    # Dictionary mapping log levels to color constants
    LEVEL_COLORS = {
        logging.DEBUG: BRIGHT_BLACK,
        logging.INFO: BLUE,
        logging.WARNING: YELLOW,
        logging.ERROR: RED,
        logging.CRITICAL: RED,
    }

    # General rules for simple log messages
    # Estes são padrões regex que podem ser aplicados à mensagem completa.
    # Certifique-se que o grupo de captura (.*?) não inclui o final da string se a regra não for para isso.
    KEYWORD_RULES: List[Tuple[str, str]] = [
        # O padrão para URLs: "http(s)://..." ou "ftp://..."
        (r'(https?://\S+)', SKY),
        # Padrões para nomes de ficheiro ou strings entre aspas genéricas
        (r'(".*?\.(mp3|m4a|mp4)")', SAPPHIRE), # Nome de ficheiro de podcast
        (r'(".*?")', ROSEWATER), # Aspas genéricas (se não for um ficheiro de podcast)
        (r'(Finished\.)', GREEN),
    ]

    def __init__(self) -> None:
        """Initializes the formatter."""
        super().__init__(fmt="{message}", datefmt="%Y-%m-%d %H:%M:%S", style='{')

    def format(self, record: logging.LogRecord) -> str:
        timestamp = self.formatTime(record, self.datefmt)
        message = record.getMessage() # Esta é a mensagem original sem cores ANSI

        # Determine a cor base para o nível de log
        default_color = self.LEVEL_COLORS.get(record.levelno, self.BLUE)
        
        # Inicia a mensagem formatada com a cor base do nível de log.
        # TODA a mensagem será inicialmente desta cor.
        formatted_message_content = message 

        # --- Tratamento de casos especiais para mensagens específicas ---
        # Estas condições aplicam cores e, se necessário, novas linhas.
        # Elas constroem a string FINAL para formatted_message_content.
        if record.msg.startswith('Loading configuration from file:'):
            pattern = r'(Loading configuration from file: )(".*?")'
            # A cor já está incluída na lambda
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
            # Aqui, a cor da URL será tratada pelas KEYWORD_RULES se quiser uma cor específica.
            # A linha principal será LAVENDER.
            formatted_message_content = f"{self.LAVENDER}    -> Source URL: \"{url}\"{self.RESET}"
        
        elif message.startswith('    -> Saved as:'):
            filename = record.args[0] if record.args else "?"
            # A cor do nome do ficheiro será tratada pelas KEYWORD_RULES.
            # A linha principal será LAVENDER.
            formatted_message_content = f"{self.LAVENDER}    -> Saved as:    \"{filename}\"{self.RESET}"
        
        elif message.startswith('Last downloaded file:'):
            filename = record.args[0] if record.args else "?"
            # A cor do nome do ficheiro será tratada pelas KEYWORD_RULES.
            # A linha principal será BLUE (nível INFO).
            formatted_message_content = f"{self.BLUE}Last downloaded file: \"{filename}\"{self.RESET}"
        
        # --- Aplicação de regras genéricas para mensagens não tratadas especificamente ---
        # OU para aplicar sub-coloração em mensagens já pré-coloridas
        # Opcional: Se quiser que as KEYWORD_RULES se apliquem a mensagens que já foram coloridas nos elifs acima,
        # precisará de tornar os elifs acima mais simples, ou aplicar as KEYWORD_RULES a 'message' e depois
        # adicionar as cores do nível de log.
        # A forma atual é: elifs coloram completamente, e o 'else' usa KEYWORD_RULES.
        # Se um elif capturar, ele ignora as KEYWORD_RULES.

        # Se a mensagem não foi tratada por nenhum elif, aplica a cor default do nível e depois as KEYWORD_RULES.
        if formatted_message_content == "": # Significa que nenhum 'elif' acima foi ativado
            formatted_message_content = message # Começa com a mensagem original

            for pattern, color in self.KEYWORD_RULES:
                try:
                    # Aplica a cor à parte correspondente do regex e reinicia para a cor do nível de log
                    formatted_message_content = re.sub(
                        pattern,
                        lambda m: f"{color}{m.group(0)}{self.RESET}{default_color}", # Colorir o match e voltar para a cor default da linha
                        formatted_message_content
                    )
                except re.error as e:
                    print(f"[Formatter] Padrão inválido de REGEX ignorado: {pattern} ({e})")
            
            # Aplica a cor default do nível de log ao restante da linha que não foi pego pelo regex
            # Nota: O re.sub já faz o reset e reaplica a cor default, então isto é uma precaução final
            formatted_message_content = f"{default_color}{formatted_message_content}{self.RESET}"


        # Adiciona informações de exceção (tracebacks) se existirem
        if record.exc_info:
            formatted_message_content += "\n" + self.formatException(record.exc_info)
        
        # Adiciona nova linha antes de certas mensagens para melhor leitura
        # (Se já tiver "\n" na formatted_message_content nos elifs, remova daqui)
        # Se quiser que todas as mensagens comecem com '\n' (exceto a primeira), adicione aqui:
        # if not formatted_message_content.startswith('\n'):
        #    formatted_message_content = '\n' + formatted_message_content


        # Divide a mensagem final em linhas e adiciona o timestamp e a cor final
        lines = formatted_message_content.splitlines()
        colored_lines = []
        for i, line in enumerate(lines):
            stripped_line = line.strip()
            if stripped_line != "":
                # Aqui, a cor do timestamp é aplicada.
                # O importante é que a cor do 'line' (já formatada) não seja anulada pelo RESET do timestamp.
                # O {self.RESET} final após o timestamp garante que a linha do log em si está na cor certa.
                colored_lines.append(
                    f"{self.MAROON}[{self.RESET}{self.PEACH}{timestamp}{self.RESET}{self.MAROON}]{self.RESET} {line}" # Não usar strip() aqui se quiser manter espaços iniciais para indentação de sub-mensagens
                )
            elif i > 0 and lines[i-1].strip() != "": # Adicionar nova linha se a anterior não era vazia
                 colored_lines.append("") # Adiciona uma linha vazia para espaçamento

        # Junta as linhas com quebras de linha e retorna
        return "\n".join(colored_lines)

def compose(*functions: Callable[[Any], Any]) -> Callable[[Any], Any]:
    """Composes single-argument functions from right to left."""
    return reduce(lambda f, g: lambda x: f(g(x)), functions)
