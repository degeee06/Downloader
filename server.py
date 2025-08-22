import os
import re
import tempfile
import requests
from flask import Flask, request, jsonify, send_file
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
    """Remove intl-xx e parâmetros extras do link do Spotify"""
    clean_url = spotify_url.split("?")[0]
    clean_url = re.sub(r"open\.spotify\.com/intl-[a-z]{2}/track/", "open.spotify.com/track/", clean_url)
    return clean_url

def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "_", name)

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

def download_audio(meta: dict) -> str:
    """Baixa do YouTube usando yt-dlp + cookies (se existirem)."""
    tempdir = tempfile.mkdtemp(prefix="ytmp3_")
    outtmpl = os.path.join(tempdir, "%(title)s.%(ext)s")

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

    # se existir cookies.txt, usar
    if os.path.exists("cookies.txt"):
        ydl_opts["cookiefile"] = "cookies.txt"

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{meta['query']}", download=True)
            if "entries" in info:
                info = info["entries"][0]
            base = ydl.prepare_filename(info)
            mp3_path = os.path.splitext(base)[0] + ".mp3"
            return mp3_path
    except Exception as e:
        print(f"[ERRO yt-dlp] {e}")
        return None

def fallback_proxy(spotify_url: str) -> str:
    """
    Proxy usando Spotidownloader (ou outro similar).
    Retorna caminho local do arquivo MP3 baixado.
    """
    try:
        api_url = f"https://api.spotidownloader.com/download?url={spotify_url}"
        r = requests.get(api_url, stream=True, timeout=60)
        if r.status_code != 200:
            return None

        tempdir = tempfile.mkdtemp(prefix="proxy_")
        mp3_path = os.path.join(tempdir, "track.mp3")

        with open(mp3_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        return mp3_path
    except Exception as e:
        print(f"[ERRO Proxy] {e}")
        return None

@app.get("/")
def health():
    return jsonify({"ok": True, "service": "spotify-downloader", "endpoints": ["/api/download"]})

@app.get("/api/download")
def download():
    spotify_url = request.args.get("spotify_url", "")
    if not spotify_url:
        return jsonify({"error": "missing spotify_url"}), 400

    try:
        meta = get_track_info(spotify_url)

        # 1º tenta com yt-dlp
        mp3_path = download_audio(meta)

        # 2º fallback → proxy Spotidownloader
        if not mp3_path:
            mp3_path = fallback_proxy(spotify_url)

        if not mp3_path:
            return jsonify({"error": "Não foi possível baixar a música"}), 500

        filename = sanitize_filename(f'{meta["artists"]} - {meta["title"]}.mp3')
        return send_file(mp3_path, as_attachment=True, download_name=filename, mimetype="audio/mpeg")
    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
