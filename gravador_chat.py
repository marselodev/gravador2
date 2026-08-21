import json
import os
import re
import socket
import subprocess
import time
import signal
from datetime import datetime, timezone

# --- CONFIGURAÇÕES ---
SERVER = "irc.chat.twitch.tv"
PORT = 6667
NICK = "justinfan12345"  # Login anônimo do IRC
CHANNEL = "#snopey"      # Canal a ser gravado (com #)
STREAMER_NAME = CHANNEL.replace("#", "")

# Limite máximo de segurança em segundos (5.5 horas) para caber no limite do GitHub Actions
TEMPO_LIMITE_MAXIMO = int(5.5 * 3600)

# Flag para controlar quando o bot deve parar de gravar e salvar o arquivo
rodando = True

def tratar_cancelamento(signum, frame):
    """Detecta quando o GitHub Actions tenta cancelar a execução e salva o arquivo antes de morrer."""
    global rodando
    print("\n[!] Sinal de interrupção recebido (Cancelado no GitHub). Salvando o chat gravado até agora...")
    rodando = False

# Associa o cancelamento do GitHub a nossa função de salvamento
signal.signal(signal.SIGINT, tratar_cancelamento)
signal.signal(signal.SIGTERM, tratar_cancelamento)

def verificar_se_esta_ao_vivo(streamer):
    """Verifica se o canal está online usando o streamlink"""
    try:
        cmd = ["streamlink", "--json", f"twitch.tv/{streamer}"]
        resultado = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if resultado.returncode == 0:
            dados = json.loads(resultado.stdout)
            if dados and "streams" in dados and dados["streams"]:
                return True
    except Exception:
        pass
    return False

def parse_irc_tags(tag_str):
    tags = {}
    if not tag_str:
        return tags
    for item in tag_str.split(";"):
        if "=" in item:
            k, v = item.split("=", 1)
            tags[k] = v if v else None
    return tags

def extrair_dados_irc(linha):
    tags = {}
    if linha.startswith("@"):
        partes = linha.split(" ", 2)
        tags_raw = partes[0][1:]
        tags = parse_irc_tags(tags_raw)
        resto = partes[1] + " " + partes[2] if len(partes) > 2 else ""
    else:
        resto = linha

    match = re.search(r"^:\w+!\w+@\w+\.tmi\.twitch\.tv PRIVMSG #[^\s]+ :(.*)$", resto)
    if match:
        mensagem = match.group(1).strip()
        display_name = tags.get("display-name") or tags.get("user-id") or "Anônimo"
        user_color = tags.get("color") or "#FFFFFF"
        return display_name, mensagem, user_color
    return None, None, None

def monitorar_e_gravar():
    print(f"Verificando se o canal {STREAMER_NAME} está ao vivo...")
    
    if not verificar_se_esta_ao_vivo(STREAMER_NAME):
        print(f"[!] Streamer {STREAMER_NAME} está OFFLINE. Encerrando o robô imediatamente.")
        return  

    print(f"\n[!] LIVE DETECTADA! Iniciando gravação do chat de {CHANNEL}...")

    sock = socket.socket()
    sock.connect((SERVER, PORT))
    
    # Timeout de 1s para permitir que o loop verifique a variável 'rodando'
    sock.settimeout(1.0)

    # Solicita capacidades avançadas da Twitch (Cores, Emotes, IDs)
    sock.send("CAP REQ :twitch.tv/tags twitch.tv/commands\r\n".encode("utf-8"))
    sock.send(f"NICK {NICK}\r\n".encode("utf-8"))
    sock.send(f"JOIN {CHANNEL}\r\n".encode("utf-8"))

    comments = []
    buffer = ""
    start_time = time.time()
    ultima_verificacao = time.time()

    print("Gravando chat em tempo real... (Pressione 'Cancel workflow' no GitHub para finalizar e salvar)")

    try:
        while rodando:
            tempo_atual = time.time()

            # 1. Proteção de limite de tempo máximo
            if (tempo_atual - start_time) >= TEMPO_LIMITE_MAXIMO:
                print("\n[!] Limite máximo de tempo atingido para esta sessão. Salvando e encerrando...")
                break

            # 2. Checa se o streamer caiu a cada 60 segundos
            if tempo_atual - ultima_verificacao >= 60:
                ultima_verificacao = tempo_atual
                if not verificar_se_esta_ao_vivo(STREAMER_NAME):
                    print("\n[!] A live foi encerrada pelo streamer. Encerrando gravação...")
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

                    if "PING" in linha:
                        sock.send("PONG :tmi.twitch.tv\r\n".encode("utf-8"))
                        continue

                    usuario, mensagem, cor_usuario = extrair_dados_irc(linha)

                    if usuario and mensagem:
                        offset_segundos = round(time.time() - start_time, 3)
                        data_atual = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

                        comentario = {
                            "_id": f"c_{len(comments) + 1}",
                            "created_at": data_atual,
                            "updated_at": data_atual,
                            "channel_id": "0",
                            "content_type": "video",
                            "content_id": "0",
                            "content_offset_seconds": offset_segundos,
                            "commenter": {
                                "display_name": usuario,
                                "_id": "0",
                                "name": usuario.lower(),
                                "type": "user",
                                "bio": None,
                                "created_at": "2020-01-01T00:00:00Z",
                                "updated_at": "2020-01-01T00:00:00Z",
                                "logo": None
                            },
                            "message": {
                                "body": mensagem,
                                "bits_spent": 0,
                                "fragments": [
                                    {
                                        "text": mensagem,
                                        "emoticon": None
                                    }
                                ],
                                "is_action": False,
                                "user_badges": [],
                                "user_color": cor_usuario
                            },
                            "source": "chat",
                            "state": "published"
                        }

                        comments.append(comentario)
                        print(f"[{offset_segundos}s] {usuario}: {mensagem}")
            
            except socket.timeout:
                # O timeout de 1s serve apenas para o código chegar aqui e o "while rodando" ser verificado novamente
                continue

    except Exception as e:
        print(f"Erro durante a gravação: {e}")

    finally:
        sock.close()

        if not comments:
            print("Nenhum comentário foi gravado. O arquivo JSON não será gerado.")
            return

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        nome_json = f"chat_{STREAMER_NAME}_{timestamp}.json"
        
        # Garante que os valores de duração e final do vídeo sejam do tipo Float
        duracao_final = float(comments[-1]["content_offset_seconds"]) if comments else 0.0

        # Estrutura JSON exata e atualizada exigida pelo TwitchDownloader
        json_compativel = {
            "FileInfo": {
                "Version": {
                    "Major": 1,
                    "Minor": 1,
                    "Build": 0,
                    "Revision": 0
                },
                "CreatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "UpdatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            },
            "streamer": {
                "name": STREAMER_NAME,
                "id": 0
            },
            "video": {
                "title": f"Chat de {CHANNEL}",
                "description": "",
                "id": "0",
                "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "start": 0.0,
                "end": duracao_final,
                "length": duracao_final,
                "viewCount": 0,
                "game": ""
            },
            "comments": comments
        }

        with open(nome_json, "w", encoding="utf-8") as f:
            json.dump(json_compativel, f, ensure_ascii=False, indent=2)

        print(f"\n[Sucesso!] Arquivo JSON do chat gerado e salvo: {nome_json}")

if __name__ == "__main__":
    monitorar_e_gravar()
