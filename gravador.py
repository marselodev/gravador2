import json
from datetime import datetime, timezone
from chatdownloader import ChatDownloader

STREAM_URL = "https://www.twitch.tv/snopey"
STREAMER_NAME = "snopey"

def gravar_chat():
    print(f"🤖 Tentando conectar ao chat do link: {STREAM_URL}")
    
    downloader = ChatDownloader()
    
    try:
        # Conecta direto na live do Snopey
        chat = downloader.get_chat(STREAM_URL)
        mensagens = []
        
        print(f"🟢 Conectado com sucesso! Gravando as mensagens em tempo real...")
        
        # Fica gravando enquanto o chat estiver ativo
        for msg in chat:
            mensagens.append(msg)
            
        # Quando a live acabar, o loop encerra e gera o JSON
        data_hoje = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M")
        nome_arquivo = f"chat_snopey_{data_hoje}.json"
        
        with open(nome_arquivo, "w", encoding="utf-8") as f:
            json.dump(mensagens, f, ensure_ascii=False, indent=4)
            
        print(f"✅ Live finalizada! Arquivo criado com sucesso: {nome_arquivo}")

    except Exception as e:
        print(f"🔴 O Snopey está OFFLINE no momento ou a live caiu. Nenhuma gravação gerada.")

if __name__ == "__main__":
    gravar_chat()
