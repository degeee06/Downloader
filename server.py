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
    duration_ms = t["duration_ms"]

    return {
        "title": title,
        "artists": artists,
        "album": album,
        "cover": cover,
        "query": query,
        "duration": duration_ms // 1000
    }

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
        ydl_opts = {"format": "bestaudio/best", "noplaylist": True, "quiet": True}
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{meta['query']}", download=False)
            if "entries" in info:
                info = info["entries"][0]
            return jsonify({
                "track": meta,
                "source": {
                    "title": info.get("title"),
                    "webpage_url": info.get("webpage_url"),
                    "direct_url": info.get("url"),  # link direto para streaming/download
                    "duration": info.get("duration"),
                }
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
