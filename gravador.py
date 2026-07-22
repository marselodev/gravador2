import json
import re
import socket
import time
from datetime import datetime, timezone

# --- CONFIGURAÇÕES ---
SERVER = "irc.chat.twitch.tv"
PORT = 6667
NICK = "justinfan12345"  # Login anônimo
CHANNEL = "#snopey"  # Canal a ser gravado
NOME_ARQUIVO = f"chat_snopey_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.json"


def extrair_dados_irc(linha):
    match = re.search(r"^:(\w+)!\w+@\w+\.tmi\.twitch\.tv PRIVMSG #[^\s]+ :(.*)$", linha)
    if match:
        return match.group(1), match.group(2).strip()
    return None, None


def iniciar_gravacao():
    print(f"Conectando ao chat do canal {CHANNEL}...")

    sock = socket.socket()
    sock.connect((SERVER, PORT))
    sock.send(f"NICK {NICK}\r\n".encode("utf-8"))
    sock.send(f"JOIN {CHANNEL}\r\n".encode("utf-8"))

    print(
        "Gravando... Pressione CTRL+C no terminal quando quiser parar e salvar."
    )

    comments = []
    buffer = ""
    start_time = time.time()  # Marca o tempo zero

    try:
        while True:
            dados = sock.recv(2048).decode("utf-8", errors="ignore")
            if not dados:
                break

            buffer += dados
            linhas = buffer.split("\r\n")
            buffer = linhas.pop()

            for linha in linhas:
                if not linha:
                    continue

                if linha.startswith("PING"):
                    sock.send("PONG :tmi.twitch.tv\r\n".encode("utf-8"))
                    continue

                usuario, mensagem = extrair_dados_irc(linha)

                if usuario and mensagem:
                    offset_segundos = round(time.time() - start_time, 3)

                    # Estrutura exata exigida pelo TwitchDownloader v1.56+
                    comentario = {
                        "_id": f"c_{len(comments) + 1}",
                        "created_at": datetime.now(timezone.utc).strftime(
                            "%Y-%m-%dT%H:%M:%SZ"
                        ),
                        "updated_at": datetime.now(timezone.utc).strftime(
                            "%Y-%m-%dT%H:%M:%SZ"
                        ),
                        "channel_id": "0",
                        "content_type": "video",
                        "content_id": "0",
                        "content_offset_seconds": offset_segundos,
                        "commenter": {
                            "display_name": usuario,
                            "_id": "0",
                            "name": usuario,
                            "type": "user",
                            "bio": None,
                            "created_at": "2020-01-01T00:00:00Z",
                            "updated_at": "2020-01-01T00:00:00Z",
                            "logo": None,
                        },
                        "message": {
                            "body": mensagem,
                            "bits_spent": 0,
                            "fragments": [{"text": mensagem, "emoticon": None}],
                            "is_action": False,
                            "user_badges": [],
                            "user_color": "#FFFFFF",
                        },
                        "source": "chat",
                        "state": "published",
                    }

                    comments.append(comentario)
                    print(f"[{offset_segundos}s] {usuario}: {mensagem}")

    except KeyboardInterrupt:
        print("\n\nEncerrando e montando arquivo JSON...")

    finally:
        sock.close()

        # Estrutura Global Padrão TwitchDownloader
        json_compativel = {
            "format": "JSON",
            "file_version": 1,
            "streamer": {"name": CHANNEL.replace("#", ""), "id": 0},
            "video": {
                "title": f"Chat de {CHANNEL}",
                "id": "0",
                "duration": (
                    comments[-1]["content_offset_seconds"] if comments else 0
                ),
                "start": 0,
                "end": (
                    comments[-1]["content_offset_seconds"] if comments else 0
                ),
            },
            "comments": comments,
        }

        # Salva o JSON final
        with open(NOME_ARQUIVO, "w", encoding="utf-8") as f:
            json.dump(json_compativel, f, ensure_ascii=False, indent=2)

        print(f"\nPRONTO! Salvo em: {NOME_ARQUIVO}")
        print("Agora pode carregar no TwitchDownloader que ele vai aceitar!")


if __name__ == "__main__":
    iniciar_gravacao()
