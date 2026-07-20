import socket
import time
import sys
import requests

CANAL = "snopey"
ARQUIVO_LOG = "chat_log.txt" 
TEMPO_LIMITE_INATIVO = 300 # 5 minutos sem mensagens após a live começar (por garantia)

def streamer_esta_ao_vivo():
    """Verifica de forma rápida e direta se o streamer está online."""
    url = f"https://www.twitch.tv/{CANAL}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        resposta = requests.get(url, headers=headers, timeout=10)
        # Se a palavra "isLiveBroadcast" estiver na página, significa que ele está online
        if "isLiveBroadcast" in resposta.text:
            return True
        return False
    except Exception:
        # Se der erro na checagem, assume True por segurança para não perder a live
        return True

def iniciar_gravacao():
    print(f"[-] Verificando se {CANAL} está ao vivo agora...")
    
    # CHECAGEM INICIAL: Se não estiver ao vivo, desliga o robô NA HORA!
    if not streamer_esta_ao_vivo():
        print(f"[!] {CANAL} está OFFLINE. Desligando o robô imediatamente para economizar minutos.")
        sys.exit(0) # Fecha o Python e o GitHub para na hora
        
    print(f"[+] {CANAL} está ONLINE! Iniciando gravação do chat...")

    server = 'irc.chat.twitch.tv'
    port = 6667
    nickname = 'justinfan12345'
    
    sock = socket.socket()
    try:
        sock.connect((server, port))
        sock.send(f"NICK {nickname}\n".encode('utf-8'))
        sock.send(f"JOIN #{CANAL}\n".encode('utf-8'))
    except Exception as e:
        print(f"Erro ao conectar ao chat: {e}")
        return

    ultima_mensagem_tempo = time.time()
    
    with open(ARQUIVO_LOG, "a", encoding="utf-8") as f:
        sock.settimeout(10.0)
        
        while True:
            try:
                resp = sock.recv(2048).decode('utf-8')
                
                if resp.startswith('PING'):
                    sock.send("PONG :tmi.twitch.tv\r\n".encode('utf-8'))
                elif len(resp) > 0:
                    ultima_mensagem_tempo = time.time()
                    f.write(resp)
                    f.flush()
            except socket.timeout:
                pass
            except Exception as e:
                print(f"Erro na conexão: {e}")
                break
                
            # Se a live cair e o chat morrer por 5 minutos, ele desliga
            if time.time() - ultima_mensagem_tempo > TEMPO_LIMITE_INATIVO:
                print("[!] O chat parou. Conferindo se a live fechou...")
                if not streamer_esta_ao_vivo():
                    print("[!] Live encerrada de verdade. Fechando o gravador!")
                    break
                else:
                    # Se ainda estiver ao vivo (só o chat que acalmou), reseta o tempo
                    ultima_mensagem_tempo = time.time()

    sock.close()

if __name__ == "__main__":
    iniciar_gravacao()
