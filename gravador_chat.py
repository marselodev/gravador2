import socket
import time

CANAL = "snopey"
ARQUIVO_LOG = "chat_log.txt" 
TEMPO_LIMITE_INATIVO = 600 # 10 minutos (600 segundos) sem mensagens = live fechou

def iniciar_gravacao():
    server = 'irc.chat.twitch.tv'
    port = 6667
    nickname = 'justinfan12345' # Conecta de forma anônima para ler o chat
    
    sock = socket.socket()
    try:
        sock.connect((server, port))
        sock.send(f"NICK {nickname}\n".encode('utf-8'))
        sock.send(f"JOIN #{CANAL}\n".encode('utf-8'))
    except Exception as e:
        print(f"Erro ao conectar ao chat: {e}")
        return

    print(f"[-] Conectado ao chat de {CANAL}. Aguardando mensagens...")
    
    ultima_mensagem_tempo = time.time()
    
    with open(ARQUIVO_LOG, "a", encoding="utf-8") as f:
        sock.settimeout(10.0) # Checa o tempo a cada 10 segundos
        
        while True:
            try:
                resp = sock.recv(2048).decode('utf-8')
                
                if resp.startswith('PING'):
                    sock.send("PONG :tmi.twitch.tv\r\n".encode('utf-8'))
                elif len(resp) > 0:
                    # Se chegou mensagem, atualiza o cronômetro
                    ultima_mensagem_tempo = time.time()
                    f.write(resp)
                    f.flush()
                    print(f"[LOG] Mensagem gravada.")
            except socket.timeout:
                pass
            except Exception as e:
                print(f"Erro na conexão: {e}")
                break
                
            # Se passar de 10 minutos sem nenhuma mensagem no chat, encerra
            if time.time() - ultima_mensagem_tempo > TEMPO_LIMITE_INATIVO:
                print("[!] Chat inativo por muito tempo. Assumindo que a live acabou!")
                break

    sock.close()

if __name__ == "__main__":
    iniciar_gravacao()
