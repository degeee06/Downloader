import os
import re
import tempfile
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

# 🔹 Recria cookies.txt a partir da variável no Render
if os.getenv("YOUTUBE_COOKIES"):
    with open("cookies.txt", "w", encoding="utf-8") as f:
        f.write(os.getenv("YOUTUBE_COOKIES"))


def sanitize_url(spotify_url: str) -> str:
    """Normaliza links do Spotify (remove intl-xx/ e parâmetros)."""
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


def search_audio_source(meta: dict):
    """Retorna apenas URL direto (não baixa)."""
    search_queries = [
        f"ytsearch10:{meta['query']}",
        f"ytmusicsearch10:{meta['query']}",
        f"scsearch10:{meta['query']}",
        f"dzsearch10:{meta['query']}",
    ]
    ydl_opts = {
        "format": "bestaudio/best",
        "noplaylist": True,
        "quiet": True,
        "cookiefile": "cookies.txt"
    }
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


def download_audio(meta: dict) -> str:
    """Baixa e retorna caminho do MP3."""
    tempdir = tempfile.mkdtemp(prefix="ytmp3_")
    outtmpl = os.path.join(tempdir, "%(title)s.%(ext)s")
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "noplaylist": True,
        "cookiefile": "cookies.txt",  # 🔹 força login
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192"
        }],
        "quiet": True,
        "no_warnings": True,
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"ytsearch1:{meta['query']}", download=True)
        if "entries" in info:
            info = info["entries"][0]
        base = ydl.prepare_filename(info)
        mp3_path = os.path.splitext(base)[0] + ".mp3"
        return mp3_path


@app.get("/")
def health():
    return jsonify({"ok": True, "service": "spotify-linker", "endpoints": ["/api/preview", "/api/source", "/api/download"]})


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
        return jsonify({"track": meta, "source": source})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.get("/api/download")
def download():
    spotify_url = request.args.get("spotify_url", "")
    if not spotify_url:
        return jsonify({"error": "missing spotify_url"}), 400
    try:
        meta = get_track_info(spotify_url)
        mp3_path = download_audio(meta)
        filename = sanitize_filename(f'{meta["artists"]} - {meta["title"]}.mp3')
        return send_file(mp3_path, as_attachment=True, download_name=filename, mimetype="audio/mpeg")
    except Exception as e:
        return jsonify({"error": str(e)}), 400


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
