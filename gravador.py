import json
import os
import platform
import re
import socket
import subprocess
import time
from datetime import datetime, timezone

# --- CONFIGURAÇÕES ---
SERVER = "irc.chat.twitch.tv"
PORT = 6667
NICK = "justinfan12345"  # Login anônimo
CHANNEL = "#snopey"  # Canal a ser gravado
TIMESTAMP = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
NOME_JSON = f"chat_snopey_{TIMESTAMP}.json"
NOME_VIDEO = f"chat_snopey_{TIMESTAMP}.mp4"


def extrair_dados_irc(linha):
    match = re.search(r"^:(\w+)!\w+@\w+\.tmi\.twitch\.tv PRIVMSG #[^\s]+ :(.*)$", linha)
    if match:
        return match.group(1), match.group(2).strip()
    return None, None


def renderizar_video_chat(json_file, output_file):
    print("\nIniciando a renderização do vídeo do chat com TwitchDownloaderCLI...")
    
    # Baixa a versão CLI do TwitchDownloader compatível com Linux se não existir
    cli_path = "./TwitchDownloaderCLI"
    if not os.path.exists(cli_path):
        print("Baixando TwitchDownloaderCLI...")
        subprocess.run([
            "curl", "-L", 
            "https://github.com/Lay295/TwitchDownloader/releases/download/1.55.0/TwitchDownloaderCLI-Linux-X64",
            "-o", cli_path
        ], check=True)
        subprocess.run(["chmod", "+x", cli_path], check=True)

    # Comando para renderizar o chat em vídeo MP4
    # Resolução padrão 400x800, fundo transparente ou cor sólida adaptada para edição
    cmd = [
        cli_path, "chatrender",
        "--input", json_file,
        "--output", output_file,
        "--resolution", "400", "800",
        "--framerate", "30",
        "--font-size", "14",
        "--background-color", "#00000000" # Fundo transparente (se o player aceitar) ou ajuste para cor sólida se preferir
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print(f"Vídeo gerado com sucesso: {output_file}")
    except subprocess.CalledProcessError as e:
        print(f"Erro ao renderizar o vídeo: {e}")


def iniciar_gravacao():
    print(f"Conectando ao chat do canal {CHANNEL}...")

    sock = socket.socket()
    sock.connect((SERVER, PORT))
    sock.send(f"NICK {NICK}\r\n".encode("utf-8"))
    sock.send(f"JOIN {CHANNEL}\r\n".encode("utf-8"))

    print("Gravando... Pressione CTRL+C no terminal quando quiser parar e salvar.")

    comments = []
    buffer = ""
    start_time = time.time()

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

                    comentario = {
                        "_id": f"c_{len(comments) + 1}",
                        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
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
        print("\n\nEncerrando...")

    finally:
        sock.close()

        if not comments:
            print("Nenhum comentário gravado.")
            return

        json_compativel = {
            "format": "JSON",
            "file_version": 1,
            "streamer": {"name": CHANNEL.replace("#", ""), "id": 0},
            "video": {
                "title": f"Chat de {CHANNEL}",
                "id": "0",
                "duration": comments[-1]["content_offset_seconds"],
                "start": 0,
                "end": comments[-1]["content_offset_seconds"],
            },
            "comments": comments,
        }

        # Salva o JSON temporário
        with open(NOME_JSON, "w", encoding="utf-8") as f:
            json.dump(json_compativel, f, ensure_ascii=False, indent=2)

        # Transforma o JSON em Vídeo MP4
        renderizar_video_chat(NOME_JSON, NOME_VIDEO)


if __name__ == "__main__":
    iniciar_gravacao()
