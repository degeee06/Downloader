import os
import tempfile
import re
from flask import Flask, request, send_file, jsonify
from dotenv import load_dotenv
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials
from yt_dlp import YoutubeDL
from flask_cors import CORS

# Carregar variáveis locais (.env)
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

def normalize_spotify_url(spotify_url: str) -> str:
    """
    Remove prefixos regionais do Spotify, ex: /intl-pt/, /br/, etc.
    """
    return re.sub(r"open\.spotify\.com/[^/]+/track/", "open.spotify.com/track/", spotify_url)

def get_track_info(spotify_url: str):
    spotify_url = normalize_spotify_url(spotify_url)

    # Extrair track_id com regex
    match = re.search(r"track/([A-Za-z0-9]+)", spotify_url)
    if not match:
        raise ValueError("Só aceito links de faixa do Spotify (open.spotify.com/track/...)")

    track_id = match.group(1)

    # Buscar metadados no Spotify
    t = sp.track(track_id)
    title = t.get("name", "Unknown Title")
    artists_list = [a["name"] for a in t.get("artists", [])]
    artist = artists_list[0] if artists_list else "Unknown Artist"
    album = t.get("album", {}).get("name", "Unknown Album")
    images = t.get("album", {}).get("images", [])
    cover = images[0]["url"] if images else None
    duration_ms = t.get("duration_ms", 0)  # duração oficial em ms
    query = f"{artist} - {title}"
    return {
        "title": title,
        "artists": artist,
        "album": album,
        "cover": cover,
        "query": query,
        "duration_ms": duration_ms
    }

def download_to_mp3_by_query(query: str, duration_ms: int) -> str:
    tempdir = tempfile.mkdtemp(prefix="ytmp3_")
    outtmpl = os.path.join(tempdir, "%(title)s.%(ext)s")
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "noplaylist": True,
        "default_search": "ytsearch10",  # busca até 10 resultados
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192"
        }],
        "quiet": True,
        "no_warnings": True,
    }

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=False)

        # Se for uma lista de resultados, escolher o mais parecido com a duração
        if "entries" in info:
            best_match = None
            best_diff = None
            for entry in info["entries"]:
                if not entry or "duration" not in entry:
                    continue
                yt_duration_ms = entry["duration"] * 1000
                diff = abs(yt_duration_ms - duration_ms)
                if best_match is None or diff < best_diff:
                    best_match = entry
                    best_diff = diff

            if best_match:
                info = ydl.extract_info(best_match["url"], download=True)
            else:
                raise ValueError(f"Nenhum vídeo público encontrado no YouTube para: {query}")

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

        try:
            # 1ª tentativa: artista + título
            mp3_path = download_to_mp3_by_query(meta["query"], meta["duration_ms"])
        except Exception:
            # fallback: só título
            mp3_path = download_to_mp3_by_query(meta["title"], meta["duration_ms"])

        filename = sanitize_filename(f'{meta["artists"]} - {meta["title"]}.mp3')
        return send_file(mp3_path, as_attachment=True, download_name=filename, mimetype="audio/mpeg")
    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
