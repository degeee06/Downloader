import os
import re
import requests
from flask import Flask, request, jsonify, redirect
from dotenv import load_dotenv
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials
from flask_cors import CORS

load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Spotify auth
sp = Spotify(auth_manager=SpotifyClientCredentials(
    client_id=os.getenv("SPOTIFY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIFY_CLIENT_SECRET")
))

def sanitize_url(spotify_url: str) -> str:
    """Normaliza links do Spotify (remove intl-xx/ e parâmetros)."""
    clean_url = spotify_url.split("?")[0]
    clean_url = re.sub(r"open\.spotify\.com/intl-[a-z]{2}/track/", "open.spotify.com/track/", clean_url)
    return clean_url

def get_track_info(spotify_url: str):
    clean_url = sanitize_url(spotify_url)
    if "open.spotify.com/track/" not in clean_url:
        raise ValueError("Só aceito links de faixa do Spotify (open.spotify.com/track/...)")

    track_id = clean_url.split("track/")[1]
    t = sp.track(track_id)
    title = t["name"]
    artists = ", ".join([a["name"] for a in t["artists"]])
    album = t["album"]["name"]
    cover = t["album"]["images"][0]["url"] if t["album"]["images"] else None
    query = f"{artists} - {title}"

    return {
        "title": title,
        "artists": artists,
        "album": album,
        "cover": cover,
        "query": query,
        "duration": t["duration_ms"] // 1000
    }

def get_mp3_link(query: str):
    """Chama a API RapidAPI YouTube MP36 para pegar MP3 pronto."""
    url = "https://youtube-mp36.p.rapidapi.com/dl"
    headers = {
        "X-RapidAPI-Key": os.getenv("RAPIDAPI_KEY"),
        "X-RapidAPI-Host": "youtube-mp36.p.rapidapi.com"
    }

    # Aqui a API espera um YouTube ID, não o texto
    # Então primeiro fazemos busca no YouTube
    search_url = "https://www.googleapis.com/youtube/v3/search"
    yt_key = os.getenv("YOUTUBE_API_KEY")  # precisa ativar YouTube Data API v3
    params = {"part": "snippet", "q": query, "key": yt_key, "maxResults": 1, "type": "video"}
    r = requests.get(search_url, params=params)
    r.raise_for_status()
    items = r.json().get("items", [])
    if not items:
        raise ValueError("Nenhum vídeo encontrado para a música")

    video_id = items[0]["id"]["videoId"]

    # Agora chamamos o RapidAPI
    r = requests.get(url, headers=headers, params={"id": video_id})
    r.raise_for_status()
    data = r.json()
    if data.get("status") != "ok":
        raise ValueError("Erro ao converter para MP3")
    return data

@app.get("/")
def health():
    return jsonify({"ok": True, "service": "spotify-mp3", "endpoints": ["/api/preview", "/api/download"]})

@app.get("/api/preview")
def preview():
    spotify_url = request.args.get("spotify_url", "")
    if not spotify_url:
        return jsonify({"error": "missing spotify_url"}), 400
    try:
        meta = get_track_info(spotify_url)
        return jsonify(meta)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.get("/api/download")
def download():
    spotify_url = request.args.get("spotify_url", "")
    if not spotify_url:
        return jsonify({"error": "missing spotify_url"}), 400
    try:
        meta = get_track_info(spotify_url)
        mp3_data = get_mp3_link(meta["query"])
        return redirect(mp3_data["link"])  # 🔥 redireciona direto pro MP3 pronto
    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
