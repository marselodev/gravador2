import sys
import os
import json
import socket
import streamlink
from datetime import datetime, timezone

STREAMER_NAME = "snopey"
STREAM_URL = f"https://www.twitch.tv/{STREAMER_NAME}"
NICK = "justinfan12345"

def live_esta_online():
    """Verifica se a live está ao vivo usando o Streamlink"""
    try:
        streams = streamlink.streams(STREAM_URL)
        return bool(streams)
    except Exception:
        return False

def gravar_chat():
    print(f"🤖 Checando se {STREAMER_NAME} está ao vivo...")
    
    if not live_esta_online():
        print(f"🔴 {STREAMER_NAME} está OFFLINE. Encerrando execução.")
        return

    print(f"🟢 Live ONLINE! Conectando ao chat de {STREAMER_NAME}...")
    
    server = "irc.chat.twitch.tv"
    port = 6667
    
    mensagens = []
    
    try:
        sock = socket.socket()
        sock.settimeout(10.0) # Timeout curto apenas para leitura rápida
        sock.connect((server, port))
        
        sock.send(f"PASS oauth:12345\r\n".encode('utf-8'))
        sock.send(f"NICK {NICK}\r\n".encode('utf-8'))
        sock.send(f"JOIN #{STREAMER_NAME}\r\n".encode('utf-8'))
        
        print(f"🎙️ Gravando chat em tempo real... (Encerrará assim que a live fechar)")
        
        contador_checagem = 0
        
        while True:
            try:
                resp = sock.recv(2048).decode('utf-8', errors='ignore')
                
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
            except socket.timeout:
                # A cada pausa no chat, ele faz uma checagem rápida se o vídeo da live caiu
                pass
            
            # A cada poucos ciclos, valida se a transmissão de vídeo continua ativa
            contador_checagem += 1
            if contador_checagem >= 5:
                contador_checagem = 0
                if not live_esta_online():
                    print("🔴 A live foi encerrada pelo streamer! Parando gravação...")
                    break

    except Exception as e:
        print(f"🔴 Conexão finalizada: {e}")
    finally:
        sock.close()
        if mensagens:
            data_hoje = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M")
            nome_arquivo = f"chat_snopey_{data_hoje}.json"
            
            with open(nome_arquivo, "w", encoding="utf-8") as f:
                json.dump(mensagens, f, ensure_ascii=False, indent=4)
                
            print(f"✅ Chat salvo com sucesso: {nome_arquivo}")
        else:
            print("🔴 Nenhuma mensagem gravada.")

if __name__ == "__main__":
    gravar_chat()
