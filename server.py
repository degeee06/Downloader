import os
import requests
from flask import Flask, request, jsonify, redirect
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")

@app.get("/")
def health():
    return jsonify({"ok": True, "service": "youtube-mp3", "endpoint": "/api/download?video_id="})

@app.get("/api/download")
def download():
    video_id = request.args.get("video_id")
    if not video_id:
        return jsonify({"error": "missing video_id"}), 400

    url = "https://youtube-mp36.p.rapidapi.com/dl"
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": "youtube-mp36.p.rapidapi.com"
    }
    query = {"id": video_id}

    r = requests.get(url, headers=headers, params=query)

    if r.status_code != 200:
        return jsonify({"error": "API request failed", "status": r.status_code}), 500

    data = r.json()
    if data.get("status") != "ok":
        return jsonify({"error": "conversion failed", "data": data}), 500

    # 🔗 retorna o link do MP3 pronto
    return jsonify({
        "title": data.get("title"),
        "duration": data.get("duration"),
        "download_url": data.get("link")
    })

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
