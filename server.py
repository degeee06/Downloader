import os
import re
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials

load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Spotify auth
sp = Spotify(auth_manager=SpotifyClientCredentials(
    client_id=os.getenv("SPOTIFY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIFY_CLIENT_SECRET")
))

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")

def sanitize_url(spotify_url: str) -> str:
    """Normaliza links do Spotify (remove intl-xx/ e parâmetros)."""
    clean_url = spotify_url.split("?")[0]
    clean_url = re.sub(r"open\.spotify\.com/intl-[a-z]{2}/track/", "open.spotify.com/track/", clean_url)
    return clean_url

def get_track_info(spotify_url: str):
    """Pega dados da faixa no Spotify."""
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

def get_youtube_mp3(query: str):
    """Usa RapidAPI YouTube-MP3 pra converter direto em MP3 pronto."""
    # Primeiro pega o video_id pelo search do YouTube
    search_url = "https://www.googleapis.com/youtube/v3/search"
    search_params = {
        "part": "snippet",
        "q": query,
        "maxResults": 1,
        "type": "video",
        "key": os.getenv("YOUTUBE_API_KEY")  # precisa de API key do YouTube Data API
    }
    r = requests.get(search_url, params=search_params)
    r.raise_for_status()
    video_id = r.json()["items"][0]["id"]["videoId"]

    # Agora pede conversão MP3 via RapidAPI
    url = "https://youtube-mp36.p.rapidapi.com/dl"
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": "youtube-mp36.p.rapidapi.com"
    }
    query = {"id": video_id}
    r2 = requests.get(url, headers=headers, params=query)
    r2.raise_for_status()
    data = r2.json()

    if data.get("status") != "ok":
        raise Exception("Falha ao converter vídeo")

    return {
        "title": data.get("title"),
        "duration": data.get("duration"),
        "download_url": data.get("link")
    }

@app.get("/")
def health():
    return jsonify({"ok": True, "service": "spotify-youtube-mp3", "endpoint": "/api/spotify-download"})

@app.get("/api/spotify-download")
def spotify_download():
    spotify_url = request.args.get("spotify_url", "")
    if not spotify_url:
        return jsonify({"error": "missing spotify_url"}), 400
    try:
        track = get_track_info(spotify_url)
        audio = get_youtube_mp3(track["query"])
        return jsonify({"track": track, "audio": audio})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
