import sys
import os
import json
import socket
from datetime import datetime, timezone

STREAMER_NAME = "snopey"
NICK = "justinfan12345"  # Login anônimo padrão da Twitch (não precisa de senha)

def gravar_chat():
    print(f"🤖 Tentando conectar ao chat da Twitch de: {STREAMER_NAME}")
    
    server = "irc.chat.twitch.tv"
    port = 6667
    
    try:
        sock = socket.socket()
        sock.connect((server, port))
        
        sock.send(f"PASS oauth:12345\r\n".encode('utf-8'))
        sock.send(f"NICK {NICK}\r\n".encode('utf-8'))
        sock.send(f"JOIN #{STREAMER_NAME}\r\n".encode('utf-8'))
        
        print(f"🟢 Conectado ao chat de {STREAMER_NAME}! Gravando em tempo real...")
        
        mensagens = []
        
        # Mantém escutando o chat
        while True:
            resp = sock.recv(2048).decode('utf-8', errors='ignore')
            
            # Responde ao "PING" da Twitch para a conexão não cair
            if resp.startswith('PING'):
                sock.send("PONG :tmi.twitch.tv\r\n".encode('utf-8'))
                continue
                
            if "PRIVMSG" in resp:
                try:
                    partes = resp.split('!', 1)
                    usuario = partes[0][1:]
                    msg_texto = resp.split(f"PRIVMSG #{STREAMER_NAME} :", 1)[1].strip()
                    
                    mensagens.append({
                        "usuario": usuario,
                        "mensagem": msg_texto,
                        "horario": datetime.now(timezone.utc).isoformat()
                    })
                except Exception:
                    pass

    except Exception as e:
        print(f"🔴 Conexão encerrada: {e}")
    finally:
        if 'mensagens' in locals() and len(mensagens) > 0:
            data_hoje = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M")
            nome_arquivo = f"chat_snopey_{data_hoje}.json"
            
            with open(nome_arquivo, "w", encoding="utf-8") as f:
                json.dump(mensagens, f, ensure_ascii=False, indent=4)
                
            print(f"✅ Chat salvo com sucesso: {nome_arquivo}")
        else:
            print(f"🔴 Nenhuma mensagem foi capturada.")

if __name__ == "__main__":
    gravar_chat()
