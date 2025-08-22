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
    return re.sub(r'[\\/*?:"<>|]', '_', name).strip() or "audio"

def extract_track_id(spotify_url: str) -> str:
    """
    Aceita:
      - https://open.spotify.com/track/<ID>
      - https://open.spotify.com/intl-pt/track/<ID>?si=...
      - https://open.spotify.com/br/track/<ID>
    IDs de track são base62 com 22 chars.
    """
    m = re.search(r"track/([A-Za-z0-9]{22})", spotify_url)
    if not m:
        raise ValueError("Só aceito links de faixa do Spotify (ex: https://open.spotify.com/track/<ID>)")
    return m.group(1)

def get_track_info(spotify_url: str):
    track_id = extract_track_id(spotify_url)
    t = sp.track(track_id)

    title = t.get("name") or "Unknown Title"
    artists_list = [a.get("name") for a in t.get("artists", []) if a.get("name")]
    # usar só o 1º artista melhora a busca
    artist_primary = artists_list[0] if artists_list else "Unknown Artist"
    album = (t.get("album") or {}).get("name") or "Unknown Album"
    images = (t.get("album") or {}).get("images") or []
    cover = images[0]["url"] if images else None
    duration_ms = t.get("duration_ms") or 0

    query = f"{artist_primary} - {title}"

    return {
        "title": title,
        "artist_primary": artist_primary,
        "artists_joined": ", ".join(artists_list) if artists_list else artist_primary,
        "album": album,
        "cover": cover,
        "query": query,
        "duration_s": int(round(duration_ms / 1000)) if duration_ms else 0
    }

def build_search_queries(meta: dict):
    q = meta["query"]
    title = meta["title"]
    artist = meta["artist_primary"]

    # variar as consultas e as fontes
    return [
        f"ytsearch15:{artist} - {title} official audio",
        f"ytsearch15:{artist} - {title} lyrics",
        f"ytsearch15:{artist} {title}",
        f"ytsearch15:{title} {artist}",
        f"ytsearch15:{title} audio",
        f"scsearch15:{artist} - {title}",
        f"scsearch15:{title} {artist}",
    ]

def choose_candidates(entries, target_duration_s: int):
    """
    Ordena entradas pela proximidade da duração da faixa do Spotify.
    Ignora entradas sem duração conhecida.
    """
    candidates = []
    for e in entries:
        if not e:
            continue
        dur = e.get("duration")
        url = e.get("webpage_url") or e.get("url")
        if not url:
            continue
        if isinstance(dur, (int, float)) and dur > 0:
            diff = abs(int(dur) - int(target_duration_s))
        else:
            # se não tem duração, manda pro fim da fila
            diff = 10**9
        title = e.get("title") or ""
        channel = e.get("channel") or e.get("uploader") or ""
        candidates.append({
            "url": url,
            "duration": int(dur) if isinstance(dur, (int, float)) else None,
            "diff": diff,
            "title": title,
            "channel": channel
        })
    # ordena por diff (quanto menor melhor)
    candidates.sort(key=lambda x: x["diff"])
    return candidates

def download_from_candidates(candidates, outtmpl, cookiefile_opt=None):
    """
    Tenta baixar na ordem dos melhores candidatos.
    Pula vídeos que exigem login/captcha.
    """
    base_opts = {
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
    if cookiefile_opt and os.path.isfile(cookiefile_opt):
        base_opts["cookiefile"] = cookiefile_opt

    last_err = None
    for c in candidates:
        try:
            with YoutubeDL(base_opts) as ydl:
                info = ydl.extract_info(c["url"], download=True)
                base = ydl.prepare_filename(info)
                return os.path.splitext(base)[0] + ".mp3"
        except Exception as e:
            msg = str(e)
            last_err = e
            # Padrões comuns do YouTube quando pede login/captcha
            if ("Sign in to confirm you're not a bot" in msg) or ("Proxy" in msg) or ("HTTP Error 403" in msg):
                print(f"[WARN] Bloqueado/captcha em: {c.get('url')} — tentando próximo...")
                continue
            else:
                print(f"[WARN] Falha ao baixar {c.get('url')}: {msg} — tentando próximo...")
                continue
    if last_err:
        raise last_err
    raise RuntimeError("Falha ao baixar: sem candidatos válidos.")

def download_to_mp3_multi(meta: dict) -> str:
    tempdir = tempfile.mkdtemp(prefix="ytmp3_")
    outtmpl = os.path.join(tempdir, "%(title)s.%(ext)s")

    # cookies opcionais (se existir no container)
    cookiefile = os.getenv("YTDLP_COOKIES", "cookies.txt")
    if not os.path.isfile(cookiefile):
        cookiefile = None

    search_list = build_search_queries(meta)
    aggregated_entries = []

    # 1) Coleta entradas de todas as buscas (sem baixar)
    probe_opts = {
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }
    if cookiefile:
        probe_opts["cookiefile"] = cookiefile

    for q in search_list:
        try:
            with YoutubeDL(probe_opts) as ydl:
                info = ydl.extract_info(q, download=False)
                if "entries" in info:
                    for e in info["entries"]:
                        if e:
                            aggregated_entries.append(e)
                else:
                    aggregated_entries.append(info)
        except Exception as e:
            print(f"[WARN] Busca falhou ({q}): {e}")

    if not aggregated_entries:
        raise ValueError(f"Nenhum resultado encontrado em YouTube/SoundCloud para: {meta['query']}")

    # 2) Ordena candidatos pela proximidade de duração
    candidates = choose_candidates(aggregated_entries, meta.get("duration_s", 0))

    # 3) Tenta baixar em ordem (pulando login/captcha)
    mp3_path = download_from_candidates(candidates, outtmpl, cookiefile_opt=cookiefile)
    return mp3_path

@app.get("/")
def health():
    return jsonify({
        "ok": True,
        "service": "multi-downloader",
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
        mp3_path = download_to_mp3_multi(meta)
        filename = sanitize_filename(f'{meta["artists_joined"]} - {meta["title"]}.mp3')
        return send_file(mp3_path, as_attachment=True, download_name=filename, mimetype="audio/mpeg")
    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
