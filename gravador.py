import json
import os
import re
import socket
import subprocess
import time
from datetime import datetime, timezone

# --- CONFIGURAÇÕES ---
SERVER = "irc.chat.twitch.tv"
PORT = 6667
NICK = "justinfan12345"  # Login anônimo
CHANNEL = "#snopey"  # Canal a ser gravado (com #)
STREAMER_NAME = CHANNEL.replace("#", "")

def verificar_se_esta_ao_vivo(streamer):
    """Verifica se o canal está online usando o streamlink"""
    try:
        cmd = ["streamlink", "--json", f"twitch.tv/{streamer}"]
        resultado = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if resultado.returncode == 0:
            dados = json.loads(resultado.stdout)
            if dados and "streams" in dados:
                return True
    except Exception:
        pass
    return False

def extrair_dados_irc(linha):
    match = re.search(r"^:(\w+)!\w+@\w+\.tmi\.twitch\.tv PRIVMSG #[^\s]+ :(.*)$", linha)
    if match:
        return match.group(1), match.group(2).strip()
    return None, None

def renderizar_video_chat(json_file, output_file):
    print("\nIniciando a renderização do vídeo do chat com TwitchDownloaderCLI...")
    cli_path = "./TwitchDownloaderCLI"
    
    if not os.path.exists(cli_path):
        print("Baixando TwitchDownloaderCLI...")
        subprocess.run([
            "curl", "-L", 
            "https://github.com/Lay295/TwitchDownloader/releases/download/1.55.0/TwitchDownloaderCLI-Linux-X64",
            "-o", cli_path
        ], check=True)
        subprocess.run(["chmod", "+x", cli_path], check=True)

    cmd = [
        cli_path, "chatrender",
        "--input", json_file,
        "--output", output_file,
        "--resolution", "400", "800",
        "--framerate", "30",
        "--font-size", "14",
        "--background-color", "#00FF00"  # Fundo verde cromaqui puro
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print(f"Vídeo gerado com sucesso: {output_file}")
    except subprocess.CalledProcessError as e:
        print(f"Erro ao renderizar o vídeo: {e}")

def monitorar_e_gravar():
    print(f"Verificando se o canal {STREAMER_NAME} está ao vivo...")
    
    # 1. Verifica uma única vez se está online
    if not verificar_se_esta_ao_vivo(STREAMER_NAME):
        print(f"[!] Streamer {STREAMER_NAME} está OFFLINE. Encerrando o robô imediatamente para economizar recursos.")
        return  # Encerra o script na hora!

    print(f"\n[!] LIVE DETECTADA! Iniciando gravação do chat de {CHANNEL}...")

    # 2. Conecta ao chat assim que a live é confirmada
    sock = socket.socket()
    sock.connect((SERVER, PORT))
    sock.send(f"NICK {NICK}\r\n".encode("utf-8"))
    sock.send(f"JOIN {CHANNEL}\r\n".encode("utf-8"))

    comments = []
    buffer = ""
    start_time = time.time()
    sock.setblocking(False)

    print("Gravando chat em tempo real...")

    try:
        while True:
            # A cada 2 minutos verifica se a live ainda está ligada
            if int(time.time() - start_time) % 120 == 0:
                if not verificar_se_esta_ao_vivo(STREAMER_NAME):
                    print("\n[!] A live foi desligada pelo streamer. Encerrando gravação...")
                    break

            try:
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
            except BlockingIOError:
                time.sleep(0.5)

    except Exception as e:
        print(f"Erro durante a gravação: {e}")

    finally:
        sock.close()

        if not comments:
            print("Nenhum comentário foi gravado durante a transmissão.")
            return

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        nome_json = f"chat_{STREAMER_NAME}_{timestamp}.json"
        nome_video = f"chat_{STREAMER_NAME}_{timestamp}.mp4"

        json_compativel = {
            "format": "JSON",
            "file_version": 1,
            "streamer": {"name": STREAMER_NAME, "id": 0},
            "video": {
                "title": f"Chat de {CHANNEL}",
                "id": "0",
                "duration": comments[-1]["content_offset_seconds"],
                "start": 0,
                "end": comments[-1]["content_offset_seconds"],
            },
            "comments": comments,
        }

        with open(nome_json, "w", encoding="utf-8") as f:
            json.dump(json_compativel, f, ensure_ascii=False, indent=2)

        renderizar_video_chat(nome_json, nome_video)

if __name__ == "__main__":
    monitorar_e_gravar()
