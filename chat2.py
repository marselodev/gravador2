import json
import os
import re
import socket
import subprocess
import time
import signal
import sys
from datetime import datetime, timezone

# Instala automaticamente a biblioteca de websocket se o GitHub Actions não tiver
try:
    import websocket
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "websocket-client"])
    import websocket

# --- CONFIGURAÇÕES KICK ---
STREAMER_NAME = "snopey"
PUSHER_KEY = "eb1d5f28038891f3a223"  # Chave pública padrão da Kick
PUSHER_CLUSTER = "us2"

# Limite máximo de segurança em segundos (5.5 horas)
TEMPO_LIMITE_MAXIMO = int(5.5 * 3600)

rodando = True

def tratar_cancelamento(signum, frame):
    """Detecta quando o GitHub Actions manda o sinal de parada e salva o arquivo."""
    global rodando
    print("\n[!] Sinal de interrupção recebido. Salvando o chat gravado até agora...")
    rodando = False

# Associa os sinais de interrupção à função de salvamento
signal.signal(signal.SIGINT, tratar_cancelamento)
signal.signal(signal.SIGTERM, tratar_cancelamento)

def verificar_se_esta_ao_vivo(streamer):
    """Verifica se o canal está online usando o streamlink na Kick"""
    try:
        cmd = ["streamlink", "--json", f"https://kick.com/{streamer}"]
        resultado = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if resultado.returncode == 0:
            dados = json.loads(resultado.stdout)
            if dados and "streams" in dados and dados["streams"]:
                return True
    except Exception:
        pass
    return False

def obter_chatroom_id(streamer):
    """Obtém o ID interno da sala de chat da Kick, necessário para conectar"""
    try:
        import urllib.request
        url = f"https://kick.com/api/v1/channels/{streamer}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as response:
            dados = json.loads(response.read().decode())
            return dados.get("chatroom", {}).get("id")
    except Exception as e:
        print(f"[!] Erro ao obter chatroom_id da Kick: {e}")
        return None

def monitorar_e_gravar():
    print(f"Verificando se o canal {STREAMER_NAME} está ao vivo na Kick...")
    
    if not verificar_se_esta_ao_vivo(STREAMER_NAME):
        print(f"[!] Streamer {STREAMER_NAME} está OFFLINE. Encerrando robô do chat.")
        return  

    chatroom_id = obter_chatroom_id(STREAMER_NAME)
    if not chatroom_id:
        print("[!] Não foi possível obter o ID do chat da Kick. Encerrando.")
        return

    print(f"\n[!] LIVE DETECTADA NA KICK! Iniciando gravação do chat (Sala: {chatroom_id})...")

    # Conectando ao servidor WebSocket da Kick (Pusher)
    ws_url = f"wss://ws-{PUSHER_CLUSTER}.pusher.com/app/{PUSHER_KEY}?protocol=7&client=js&version=7.4.0&flash=false"
    ws = websocket.create_connection(ws_url, timeout=10)

    # Inscrevendo no canal de chat específico do streamer
    subscribe_msg = {
        "event": "pusher:subscribe",
        "data": {"auth": "", "channel": f"chatrooms.{chatroom_id}.v2"}
    }
    ws.send(json.dumps(subscribe_msg))

    comments = []
    start_time = time.time()
    ultima_verificacao = time.time()

    try:
        while rodando:
            tempo_atual = time.time()

            if (tempo_atual - start_time) >= TEMPO_LIMITE_MAXIMO:
                print("\n[!] Limite máximo de tempo atingido. Salvando e encerrando...")
                break

            if tempo_atual - ultima_verificacao >= 60:
                ultima_verificacao = tempo_atual
                if not verificar_se_esta_ao_vivo(STREAMER_NAME):
                    print("\n[!] A live foi encerrada pelo streamer. Encerrando gravação...")
                    break

            try:
                ws.settimeout(2.0)
                raw_msg = ws.recv()
                if not raw_msg:
                    continue

                msg_data = json.loads(raw_msg)
                event = msg_data.get("event")

                # Se for uma mensagem de chat
                if event == "App\\Events\\ChatMessageEvent":
                    data_inner = json.loads(msg_data.get("data", "{}"))
                    usuario = data_inner.get("sender", {}).get("username", "Anônimo")
                    mensagem = data_inner.get("content", "")
                    cor_usuario = data_inner.get("sender", {}).get("identity", {}).get("color", "#FFFFFF")

                    if mensagem:
                        offset_segundos = round(time.time() - start_time, 3)
                        data_atual = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

                        comentario = {
                            "_id": f"c_{len(comments) + 1}",
                            "created_at": data_atual,
                            "updated_at": data_atual,
                            "channel_id": str(chatroom_id),
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

                # Mantém a conexão viva (Ping/Pong)
                elif event == "pusher:ping":
                    ws.send(json.dumps({"event": "pusher:pong", "data": {}}))

            except websocket.WebSocketTimeoutException:
                continue

    except Exception as e:
        print(f"Erro durante a gravação: {e}")

    finally:
        try:
            ws.close()
        except Exception:
            pass

        if not comments:
            print("Nenhum comentário foi gravado. O arquivo JSON não será gerado.")
            return
            
        data_simples = datetime.now().strftime("%d-%m-%Y")
        nome_json = f"chat_{STREAMER_NAME}_{data_simples}.json"
        
        duracao_final = float(comments[-1]["content_offset_seconds"]) if comments else 0.0

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
                "id": chatroom_id
            },
            "video": {
                "title": f"Chat de {STREAMER_NAME} na Kick",
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

        print(f"\n[Sucesso!] Arquivo JSON do chat da Kick gerado e salvo: {nome_json}")

if __name__ == "__main__":
    monitorar_e_gravar()
