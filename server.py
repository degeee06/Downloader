import os
import tempfile
import re
import requests
from flask import Flask, request, send_file, jsonify
from dotenv import load_dotenv
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials
from yt_dlp import YoutubeDL
from flask_cors import CORS
from pyngrok import ngrok   # 👈 adicionado
from pyngrok import ngrok, conf

conf.get_default().auth_token = "31fWDUIOBVxD5nj9asyjTFQcu0t_36cuLjwv67VVhwVXS252G"

load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Spotify auth (apenas para metadados via Client Credentials)
sp = Spotify(auth_manager=SpotifyClientCredentials(
    client_id=os.getenv("SPOTIFY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIFY_CLIENT_SECRET")
))

def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', '_', name)

def normalize_spotify_url(url: str) -> str:
    """Aceita URI, encurtador e embed, e retorna sempre no formato /track/..."""
    # URI do app (spotify:track:ID)
    if url.startswith("spotify:"):
        parts = url.split(":")
        if len(parts) == 3 and parts[1] == "track":
            return f"https://open.spotify.com/track/{parts[2]}"

    # Remove embed
    url = url.replace("/embed/", "/")

    # Resolver encurtador spotify.link
    if "spotify.link" in url:
        try:
            r = requests.head(url, allow_redirects=True, timeout=5)
            url = r.url
        except Exception:
            pass

    # Remove prefixos de localidade tipo /intl-pt/, /intl-en/, etc.
    url = re.sub(r"/intl-[a-z]{2}/", "/", url)

    return url

def get_track_info(spotify_url: str):
    spotify_url = normalize_spotify_url(spotify_url)

    if "open.spotify.com/track/" not in spotify_url:
        raise ValueError("Só aceito links de faixa do Spotify (open.spotify.com/track/...)")

    track_id = spotify_url.split("track/")[1].split("?")[0]
    t = sp.track(track_id)
    title = t["name"]
    artists = ", ".join([a["name"] for a in t["artists"]])
    album = t["album"]["name"]
    cover = t["album"]["images"][0]["url"] if t["album"]["images"] else None
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
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
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
    return jsonify({"ok": True, "service": "oujey-downloader", "endpoints": ["/api/preview", "/api/download"]})

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

    # 🔥 abre túnel do ngrok automaticamente
    public_url = ngrok.connect(port)
    print(f"🌍 Servidor público disponível em: {public_url}")

    # inicia Flask
    app.run(host="0.0.0.0", port=port, debug=False)
