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
from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC, ID3NoHeaderError
from mutagen.mp3 import MP3
import requests

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
    if url.startswith("spotify:"):
        parts = url.split(":")
        if len(parts) == 3 and parts[1] == "track":
            return f"https://open.spotify.com/track/{parts[2]}"

    url = url.replace("/embed/", "/")

    if "spotify.link" in url:
        try:
            r = requests.head(url, allow_redirects=True, timeout=5)
            url = r.url
        except Exception:
            pass

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

def add_id3_tags(mp3_path, meta):
    try:
        audio = MP3(mp3_path, ID3=ID3)

        try:
            audio.add_tags()
        except ID3NoHeaderError:
            pass

        # 🔹 Limpamos tags antigas pra evitar lixo
        audio.tags.clear()

        # 🔹 Título
        audio.tags.add(TIT2(encoding=3, text=meta.get("title", "")))
        # 🔹 Artistas
        audio.tags.add(TPE1(encoding=3, text=meta.get("artists", "")))
        # 🔹 Álbum
        audio.tags.add(TALB(encoding=3, text=meta.get("album", "")))

        # 🔹 Capa (cover)
        if meta.get("cover"):
            try:
                # Baixa a imagem em stream → mais leve que requests.get().content
                with requests.get(meta["cover"], stream=True, timeout=10) as r:
                    r.raise_for_status()
                    img_data = r.content

                # Detecta mime type (jpeg/png)
                mime = "image/jpeg"
                if meta["cover"].endswith(".png"):
                    mime = "image/png"

                audio.tags.add(APIC(
                    encoding=3,
                    mime=mime,
                    type=3,      # 3 = capa frontal
                    desc="Cover",
                    data=img_data
                ))
            except Exception as e:
                print(f"⚠️ Erro ao baixar capa: {e}")

        # 🔹 Salva tags no formato mais compatível
        audio.save(v2_version=3, v23_sep=' / ')

    except Exception as e:
        print("⚠️ Erro ao adicionar tags:", e)


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

        # 🔹 Aqui adiciona as tags ID3 + capa
        add_id3_tags(mp3_path, meta)

        filename = sanitize_filename(f'{meta["artists"]} - {meta["title"]}.mp3')
        return send_file(mp3_path, as_attachment=True, download_name=filename, mimetype="audio/mpeg")
    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))

    # Só abre ngrok localmente (Railway já fornece URL pública)
    if os.getenv("RAILWAY_ENVIRONMENT") is None:
        try:
            from pyngrok import ngrok, conf
            conf.get_default().auth_token = "SEU_TOKEN_NGROK"
            public_url = ngrok.connect(port)
            print(f"🌍 Servidor público disponível em: {public_url}")
        except Exception as e:
            print("⚠️ Ngrok não inicializado:", e)

    app.run(host="0.0.0.0", port=port, debug=False)


