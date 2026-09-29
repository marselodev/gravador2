import json
import os
import sys
import time
import signal
import subprocess
from datetime import datetime, timezone

# Garante a instalação do websocket-client
try:
    import websocket
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "websocket-client"])
    import websocket

STREAMER_NAME = "snopey"
PUSHER_KEY = "eb1d5f28038891f3a223"
PUSHER_CLUSTER = "us2"
TEMPO_LIMITE_MAXIMO = int(5.5 * 3600)

rodando = True
comments = []
chatroom_id = None

def tratar_cancelamento(signum, frame):
    global rodando
    print("\n[!] Sinal de interrupção (SIGINT/SIGTERM) recebido. A guardar chat...")
    rodando = False

signal.signal(signal.SIGINT, tratar_cancelamento)
signal.signal(signal.SIGTERM, tratar_cancelamento)

def obter_chatroom_id(streamer):
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

def salvar_json_final():
    if not comments:
        print("[!] Nenhum comentário gravado. O ficheiro JSON não será criado.")
        return

    data_simples = datetime.now().strftime("%d-%m-%Y")
    nome_json = f"chat_{STREAMER_NAME}_{data_simples}.json"
    duracao_final = float(comments[-1]["content_offset_seconds"]) if comments else 0.0

    json_compativel = {
        "FileInfo": {
            "Version": {"Major": 1, "Minor": 1, "Build": 0, "Revision": 0},
            "CreatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "UpdatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        },
        "streamer": {"name": STREAMER_NAME, "id": chatroom_id or 0},
        "video": {
            "title": f"Chat de {STREAMER_NAME} (Kick)",
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

    print(f"\n[Sucesso!] Ficheiro de chat gravado: {nome_json} ({len(comments)} mensagens)")

def monitorar_e_gravar():
    global chatroom_id
    chatroom_id = obter_chatroom_id(STREAMER_NAME)
    
    if not chatroom_id:
        print("[!] Erro: Não foi possível obter o ID do chat da Kick.")
        return

    print(f"[!] ID do Chat Kick encontrado: {chatroom_id}. A iniciar escuta do WebSocket...")

    ws_url = f"wss://ws-{PUSHER_CLUSTER}.pusher.com/app/{PUSHER_KEY}?protocol=7&client=js&version=7.4.0&flash=false"
    
    start_time = time.time()

    try:
        ws = websocket.create_connection(ws_url, timeout=10)
        subscribe_msg = {
            "event": "pusher:subscribe",
            "data": {"auth": "", "channel": f"chatrooms.{chatroom_id}.v2"}
        }
        ws.send(json.dumps(subscribe_msg))
        print("[!] Conectado com sucesso ao chat da Kick!")

        while rodando:
            if (time.time() - start_time) >= TEMPO_LIMITE_MAXIMO:
                print("\n[!] Limite máximo de tempo atingido.")
                break

            try:
                ws.settimeout(2.0)
                raw_msg = ws.recv()
                if not raw_msg:
                    continue

                msg_data = json.loads(raw_msg)
                event = msg_data.get("event")

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
                                "fragments": [{"text": mensagem, "emoticon": None}],
                                "is_action": False,
                                "user_badges": [],
                                "user_color": cor_usuario
                            },
                            "source": "chat",
                            "state": "published"
                        }
                        comments.append(comentario)
                        print(f"[{offset_segundos}s] {usuario}: {mensagem}", flush=True)

                elif event == "pusher:ping":
                    ws.send(json.dumps({"event": "pusher:pong", "data": {}}))

            except websocket.WebSocketTimeoutException:
                continue
            except Exception as e:
                print(f"[!] Erro ao receber mensagem do WebSocket: {e}")
                time.sleep(1)

    except Exception as e:
        print(f"[!] Erro de conexão WebSocket: {e}")

    finally:
        try:
            ws.close()
        except Exception:
            pass
        salvar_json_final()

if __name__ == "__main__":
    monitorar_e_gravar()
