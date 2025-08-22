import os
import re
import requests
from flask import Flask, request, jsonify, send_file
from dotenv import load_dotenv
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials
from flask_cors import CORS
import tempfile

load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Spotify auth
sp = Spotify(auth_manager=SpotifyClientCredentials(
    client_id=os.getenv("SPOTIFY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIFY_CLIENT_SECRET")
))

def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "_", name)

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

    return {"title": title, "artists": artists, "album": album, "cover": cover, "query": query}

def fetch_external_mp3(query: str):
    """
    Retorna link direto do mp3 usando serviço externo (vevioz).
    """
    query_encoded = requests.utils.quote(query)
    return f"https://api.vevioz.com/api/button/mp3/{query_encoded}"

@app.get("/")
def health():
    return jsonify({
        "ok": True,
        "service": "spotify-proxy-downloader",
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
        external_url = fetch_external_mp3(meta["query"])

        r = requests.get(external_url, stream=True)
        if r.status_code != 200:
            return jsonify({"error": "falha ao baixar do serviço externo"}), 500

        tempdir = tempfile.mkdtemp()
        filename = sanitize_filename(f"{meta['artists']} - {meta['title']}.mp3")
        filepath = os.path.join(tempdir, filename)

        with open(filepath, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

        return send_file(filepath, as_attachment=True, download_name=filename, mimetype="audio/mpeg")

    except Exception as e:
        return jsonify({"error": str(e)}), 400


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
