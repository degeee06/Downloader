import os
import re
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")

def extract_video_id(url: str) -> str:
    """Extrai video_id de links do YouTube."""
    # formatos aceitos: youtu.be/XXXX, youtube.com/watch?v=XXXX
    patterns = [
        r"(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})"
    ]
    for p in patterns:
        match = re.search(p, url)
        if match:
            return match.group(1)
    return None

@app.get("/")
def health():
    return jsonify({"ok": True, "service": "youtube-mp3", "endpoint": "/api/download?youtube_url="})

@app.get("/api/download")
def download():
    youtube_url = request.args.get("youtube_url")
    if not youtube_url:
        return jsonify({"error": "missing youtube_url"}), 400

    video_id = extract_video_id(youtube_url)
    if not video_id:
        return jsonify({"error": "invalid youtube url"}), 400

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

    return jsonify({
        "title": data.get("title"),
        "duration": data.get("duration"),
        "download_url": data.get("link")
    })

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
