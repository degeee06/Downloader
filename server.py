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


# 🔹 Extrair ID do vídeo (se for URL completa ou só id)
def extract_video_id(url_or_id: str) -> str:
    # Se for só id
    if re.match(r"^[a-zA-Z0-9_-]{11}$", url_or_id):
        return url_or_id
    # Se for URL do YouTube
    match = re.search(r"(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})", url_or_id)
    if match:
        return match.group(1)
    return None


# 🔹 Rota para baixar/converter
@app.route("/download", methods=["GET"])
def download():
    video_id = None

    # Pode vir como ?id= ou ?url=
    if "id" in request.args:
        video_id = extract_video_id(request.args.get("id"))
    elif "url" in request.args:
        video_id = extract_video_id(request.args.get("url"))

    if not video_id:
        return jsonify({"error": "É necessário passar ?id=VIDEO_ID ou ?url=YOUTUBE_URL"}), 400

    url = "https://youtube-mp36.p.rapidapi.com/dl"
    querystring = {"id": video_id}
    headers = {
        "x-rapidapi-host": "youtube-mp36.p.rapidapi.com",
        "x-rapidapi-key": RAPIDAPI_KEY,
    }

    try:
        response = requests.get(url, headers=headers, params=querystring)
        data = response.json()

        # Garantir resposta padronizada
        if data.get("status") != "ok":
            return jsonify({"error": "Falha ao converter vídeo", "details": data}), 500

        return jsonify({
            "status": "ok",
            "title": data.get("title"),
            "link": data.get("link"),
            "id": video_id,
            "thumbnail": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
