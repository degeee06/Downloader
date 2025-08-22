import os
import tempfile
import re
from flask import Flask, request, send_file, jsonify
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

def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', '_', name)

def get_track_info(spotify_url: str):
    # Regex aceita tanto /track/ quanto /intl-xx/track/
    match = re.search(r"track/([a-zA-Z0-9]+)", spotify_url)
    if not match:
        raise ValueError("Só aceito links de faixa do Spotify (open.spotify.com/track/...)")

    track_id = match.group(1)
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

def download_to_mp3_by_query(meta: dict) -> str:
    tempdir = tempfile.mkdtemp(prefix="ytmp3_")
    outtmpl = os.path.join(tempdir, "%(title)s.%(ext)s")

    # tenta múltiplos backends
    search_queries = [
        f"ytsearch10:{meta['query']}",          # YouTube normal
        f"ytsearch10:{meta['query']} audio",    # YouTube forçando áudio
        f"ytmusicsearch10:{meta['query']}",     # YouTube Music
        f"scsearch10:{meta['query']}",          # SoundCloud
        f"dzsearch10:{meta['query']}",          # Deezer (se disponível)
    ]

    for q in search_queries:
        try:
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": outtmpl,
                "noplaylist": True,
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192"
                }],
                "quiet": True,
                "no_warnings": True,
            }
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(q, download=True)
                if "entries" in info:
                    info = info["entries"][0]

                base = ydl.prepare_filename(info)
                mp3_path = os.path.splitext(base)[0] + ".mp3"

                # filtrar por duração (±10s)
                if abs(info.get("duration", 0) - meta["duration"]) <= 10:
                    return mp3_path
                else:
                    # mesmo fora da duração, retorna como fallback
                    return mp3_path
        except Exception as e:
            print(f"[WARN] Falhou em {q}: {e}")
            continue

    raise Exception(f"Nenhum resultado encontrado em YouTube/SoundCloud/Deezer para: {meta['query']}")

@app.get("/")
def health():
    return jsonify({"ok": True, "service": "multi-downloader", "endpoints": ["/api/preview", "/api/download"]})

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
        mp3_path = download_to_mp3_by_query(meta)
        filename = sanitize_filename(f'{meta["artists"]} - {meta["title"]}.mp3')
        return send_file(mp3_path, as_attachment=True, download_name=filename, mimetype="audio/mpeg")
    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)

