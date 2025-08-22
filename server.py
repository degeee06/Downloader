import os
import tempfile
import re
from flask import Flask, request, send_file, jsonify
from dotenv import load_dotenv
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials
from yt_dlp import YoutubeDL
from flask_cors import CORS

# Carregar variáveis locais (para rodar localmente com .env)
load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Spotify auth (Client Credentials flow)
sp = Spotify(auth_manager=SpotifyClientCredentials(
    client_id=os.getenv("SPOTIFY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIFY_CLIENT_SECRET")
))

def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', '_', name)

def normalize_spotify_url(spotify_url: str) -> str:
    """
    Remove prefixos de localização do Spotify, ex: /intl-pt/, /br/, /us/ etc.
    Ex: https://open.spotify.com/intl-pt/track/XYZ → https://open.spotify.com/track/XYZ
    """
    return re.sub(r"open\.spotify\.com/[^/]+/track/", "open.spotify.com/track/", spotify_url)

def get_track_info(spotify_url: str):
    spotify_url = normalize_spotify_url(spotify_url)

    # Extrair o track ID com regex
    match = re.search(r"track/([A-Za-z0-9]+)", spotify_url)
    if not match:
        raise ValueError("Só aceito links de faixa do Spotify (open.spotify.com/track/...)")

    track_id = match.group(1)

    # Buscar metadados no Spotify
    t = sp.track(track_id)
    title = t.get("name", "Unknown Title")
    artists = ", ".join([a["name"] for a in t.get("artists", [])]) or "Unknown Artist"
    album = t.get("album", {}).get("name", "Unknown Album")
    images = t.get("album", {}).get("images", [])
    cover = images[0]["url"] if images else None
    query = f"{artists} - {title}"
    return {"title": title, "artists": artists, "album": album, "cover": cover, "query": query}

def download_to_mp3_by_query(query: str) -> str:
    tempdir = tempfile.mkdtemp(prefix="ytmp3_")
    outtmpl = os.path.join(tempdir, "%(title)s.%(ext)s")
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "noplaylist": True,
        "default_search": "ytsearch1",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192"
        }],
        "quiet": True,
        "no_warnings": True,
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=True)
        if "entries" in info:
            info = info["entries"][0]
        base = ydl.prepare_filename(info)
        mp3_path = os.path.splitext(base)[0] + ".mp3"
        return mp3_path

@app.get("/")
def health():
    return jsonify({
        "ok": True,
        "service": "oujey-downloader",
        "endpoints": ["/api/preview", "/api/download"]
    })

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
        mp3_path = download_to_mp3_by_query(meta["query"])
        filename = sanitize_filename(f'{meta["artists"]} - {meta["title"]}.mp3')
        return send_file(mp3_path, as_attachment=True, download_name=filename, mimetype="audio/mpeg")
    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
