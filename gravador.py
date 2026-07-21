import os
import time
import requests
import json
from datetime import datetime, timezone
from chatdownloader import ChatDownloader

# Link direto e canal do streamer Snopey
STREAM_URL = "https://www.twitch.tv/snopey"
STREAMER_NAME = "snopey"

CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")

def get_twitch_token():
    """Obtém o token de acesso para a API da Twitch."""
    url = "https://id.twitch.tv/oauth2/token"
    params = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "client_credentials"
    }
    response = requests.post(url, params=params)
    data = response.json()
    return data.get("access_token")

def is_live(token):
    """Verifica se o canal do Snopey está ao vivo."""
    headers = {
        "Client-ID": CLIENT_ID,
        "Authorization": f"Bearer {token}"
    }
    url = f"https://api.twitch.tv/helix/streams?user_login={STREAMER_NAME}"
    response = requests.get(url, headers=headers)
    data = response.json()
    return len(data.get("data", [])) > 0

def gravar_chat():
    token = get_twitch_token()
    
    print(f"🤖 Monitorando a live no link: {STREAM_URL}")
    
    if not is_live(token):
        print(f"🔴 O Snopey está OFFLINE no momento. Encerrando o robô.")
        return False

    print(f"🟢 O Snopey está AO VIVO! Conectando ao chat...")
    
    downloader = ChatDownloader()
    
    try:
        # Puxa as mensagens em tempo real da URL do Snopey
        chat = downloader.get_chat(STREAM_URL)
        mensagens = []
        
        # O robô fica rodando e acumulando mensagens enquanto a live durar
        for msg in chat:
            mensagens.append(msg)
            
        # Quando a live terminar, ele encerra e salva o arquivo com a data de hoje
        data_hoje = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M")
        nome_arquivo = f"chat_snopey_{data_hoje}.json"
        
        with open(nome_arquivo, "w", encoding="utf-8") as f:
            json.dump(mensagens, f, ensure_ascii=False, indent=4)
            
        print(f"✅ Live finalizada! Arquivo salvo com sucesso: {nome_arquivo}")
        return True

    except Exception as e:
        print(f"❌ Ocorreu um erro durante a gravação: {e}")
        return False

if __name__ == "__main__":
    gravar_chat()
