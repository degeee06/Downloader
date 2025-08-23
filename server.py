import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/")
def home():
    return jsonify({"status": "server running"})

@app.route("/download")
def download():
    video_id = request.args.get("id")
    if not video_id:
        return jsonify({"error": "missing video id"}), 400

    # Chamada para a API do RapidAPI
    url = "https://youtube-media-downloader.p.rapidapi.com/v2/video/details"
    querystring = {
        "videoId": video_id,
        "urlAccess": "normal",
        "videos": "auto",
        "audios": "auto"
    }

    headers = {
        "x-rapidapi-key": os.getenv("RAPIDAPI_KEY"),
        "x-rapidapi-host": "youtube-media-downloader.p.rapidapi.com"
    }

    try:
        response = requests.get(url, headers=headers, params=querystring, timeout=15)
        data = response.json()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # Pegar o primeiro link de áudio disponível
    audio_url = None
    if "audios" in data and isinstance(data["audios"], list) and len(data["audios"]) > 0:
        audio_url = data["audios"][0].get("url")

    return jsonify({
        "title": data.get("title"),
        "audio_url": audio_url
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
