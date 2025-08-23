import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from dotenv import load_dotenv

# Carregar variáveis do .env
load_dotenv()

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")

app = Flask(__name__)
CORS(app)

@app.route("/")
def home():
    return "✅ API YouTube Downloader online"

@app.route("/download")
def download():
    video_id = request.args.get("id")
    if not video_id:
        return jsonify({"error": "missing id"}), 400

    url = "https://youtube-media-downloader.p.rapidapi.com/v2/video/details"
    querystring = {
        "videoId": video_id,
        "urlAccess": "normal",
        "videos": "auto",
        "audios": "auto"
    }
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": "youtube-media-downloader.p.rapidapi.com"
    }

    try:
        response = requests.get(url, headers=headers, params=querystring)
        data = response.json()

        # Pegar o primeiro áudio
        audio_url = data["audios"][0]["url"]

        return jsonify({
            "videoId": video_id,
            "title": data.get("title"),
            "audio_url": audio_url
        })

    except Exception as e:
        return jsonify({
            "error": str(e),
            "raw_response": response.text if 'response' in locals() else None
        }), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
