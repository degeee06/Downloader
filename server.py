import os
import re
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials
from yt_dlp import YoutubeDL
from flask_cors import CORS

load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Spotify auth
sp = Spotify(auth_manager=SpotifyClientCredentials(
    client_id=os.getenv("SPOTIFY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIFY_CLIENT_SECRET")
))

def get_track_info(spotify_url: str):
    if "open.spotify.com/track/" not in spotify_url:
        raise ValueError("Só aceito links de faixa do Spotify (open.spotify.com/track/...)")

    track_id = spotify_url.split("track/")[1].split("?")[0]
    t = sp.track(track_id)
    title = t["name"]
    artists = ", ".join([a["name"] for a in t["artists"]])
    album = t["album"]["name"]
    cover = t["album"]["images"][0]["url"] if t["album"]["images"] else None
    query = f"{artists} - {title}"
    duration_ms = t["duration_ms"]

    return {
        "title": title,
        "artists": artists,
        "album": album,
        "cover": cover,
        "query": query,
        "duration": duration_ms // 1000
    }

def search_audio_source(meta: dict):
    """Retorna apenas URL direto (não baixa)."""
    search_queries = [
        f"ytsearch10:{meta['query']}",
        f"ytmusicsearch10:{meta['query']}",
        f"scsearch10:{meta['query']}",
        f"dzsearch10:{meta['query']}",
    ]

    ydl_opts = {"format": "bestaudio/best", "noplaylist": True, "quiet": True}
    with YoutubeDL(ydl_opts) as ydl:
        for q in search_queries:
            try:
                info = ydl.extract_info(q, download=False)
                if "entries" in info:
                    info = info["entries"][0]

                url = info.get("url")
                if url:
                    return {
                        "source": info.get("extractor_key"),
                        "title": info.get("title"),
                        "webpage_url": info.get("webpage_url"),
                        "direct_url": url,
                        "duration": info.get("duration"),
                    }
            except Exception as e:
                print(f"[WARN] Falhou em {q}: {e}")
                continue
    return None

@app.get("/")
def health():
    return jsonify({"ok": True, "service": "spotify-linker", "endpoints": ["/api/preview", "/api/source"]})

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

@app.get("/api/source")
def source():
    spotify_url = request.args.get("spotify_url", "")
    if not spotify_url:
        return jsonify({"error": "missing spotify_url"}), 400
    try:
        meta = get_track_info(spotify_url)
        source = search_audio_source(meta)
        if not source:
            return jsonify({"error": "nenhuma fonte encontrada"}), 404
        return jsonify({
            "track": meta,
            "source": source
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
