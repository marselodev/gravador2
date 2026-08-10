import json, re, socket, subprocess, time
from datetime import datetime

STREAMER = "snopey"
CHANNEL = f"#{STREAMER}"
SERVER, PORT = "irc.chat.twitch.tv", 6667

def esta_online():
    res = subprocess.run(["streamlink", "--json", f"twitch.tv/{STREAMER}"], capture_output=True, text=True)
    return "streams" in res.stdout and len(json.loads(res.stdout).get("streams", {})) > 0

if not esta_online():
    print(f"[!] {STREAMER} está offline. Encerrando.")
    exit()

sock = socket.socket()
sock.connect((SERVER, PORT))
sock.send(f"CAP REQ :twitch.tv/tags\r\nNICK justinfan12345\r\nJOIN {CHANNEL}\r\n".encode())

comments, start_time, buffer = [], time.time(), ""
print(f"Gravando chat de {STREAMER}... (Pressione Ctrl+C para encerrar)")

try:
    while True:
        dados = sock.recv(4096).decode("utf-8", errors="ignore")
        if not dados: break
        
        buffer += dados
        linhas = buffer.split("\r\n")
        buffer = linhas.pop()

        for linha in linhas:
            if linha.startswith("PING"):
                sock.send(f"{linha.replace('PING', 'PONG')}\r\n".encode())
            elif "PRIVMSG" in linha:
                offset = round(time.time() - start_time, 3)
                user = re.search(r"display-name=([^;]+)", linha)
                nick = user.group(1) if user else "Anonimo"
                msg = linha.split(" :", 1)[-1].strip()

                comments.append({
                    "_id": f"c_{len(comments)+1}",
                    "content_offset_seconds": offset,
                    "commenter": {"display_name": nick, "name": nick.lower()},
                    "message": {"body": msg, "fragments": [{"text": msg}]}
                })
                print(f"[{offset}s] {nick}: {msg}")

except (KeyboardInterrupt, Exception) as e:
    print(f"\nFinalizando gravação: {e}")
finally:
    sock.close()
    if comments:
        duracao = comments[-1]["content_offset_seconds"]
        nome_arquivo = f"chat_{STREAMER}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        dados_json = {
            "format": "JSON", "file_version": 1,
            "streamer": {"name": STREAMER},
            "video": {"duration": str(duracao)},
            "comments": comments
        }
        
        with open(nome_arquivo, "w", encoding="utf-8") as f:
            json.dump(dados_json, f, ensure_ascii=False, indent=2)
        print(f"[Sucesso!] {len(comments)} mensagens salvas em: {nome_arquivo}")
