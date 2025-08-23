import os
import re
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Carregar variáveis de ambiente (.env no Render)
load_dotenv()

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")

app = Flask(__name__)
CORS(app)

# 🔹 Rota inicial para health check
@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "server running"})


# 🔹 Extrair ID do vídeo (aceita url ou id)
def extract_video_id(url_or_id: str) -> str:
    if re.match(r"^[a-zA-Z0-9_-]{11}$", url_or_id):
        return url_or_id
    match = re.search(r"(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})", url_or_id)
    if match:
        return match.group(1)
    return None


# 🔹 Rota para baixar/converter
@app.route("/download", methods=["GET"])
def download():
    video_id = None

    if "id" in request.args:
        video_id = extract_video_id(request.args.get("id"))
    elif "url" in request.args:
        video_id = extract_video_id(request.args.get("url"))

    if not video_id:
        return jsonify({"error": "Passe ?id=VIDEO_ID ou ?url=YOUTUBE_URL"}), 400

    url = "https://youtube-media-downloader.p.rapidapi.com/v2/video/details"
    querystring = {"videoId": video_id}
    headers = {
        "x-rapidapi-host": "youtube-media-downloader.p.rapidapi.com",
        "x-rapidapi-key": RAPIDAPI_KEY,
    }

    try:
        response = requests.get(url, headers=headers, params=querystring)
        data = response.json()
        # 👇 Essa API retorna várias opções de stream (mp4, mp3, etc)
        audio_links = [
            stream for stream in data.get("links", []) if stream.get("type") == "audio"
        ]

        if not audio_links:
            return jsonify({"error": "Nenhum link de áudio encontrado", "raw": data}), 404

        # pegar o primeiro mp3 disponível
        mp3 = next((a for a in audio_links if "mp3" in a.get("quality", "").lower()), audio_links[0])

        return jsonify({
            "status": "ok",
            "title": data.get("title"),
            "thumbnail": data.get("thumbnails", [{}])[-1].get("url"),
            "id": video_id,
            "link": mp3.get("url")
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
