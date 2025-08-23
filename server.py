import os
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Carregar variáveis de ambiente (.env no Render)
load_dotenv()

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")

app = Flask(__name__)
CORS(app)

# Rota principal para converter vídeo YouTube → MP3
@app.route("/download", methods=["GET"])
def download():
    video_id = request.args.get("id")
    if not video_id:
        return jsonify({"error": "É necessário passar ?id=VIDEO_ID"}), 400

    url = "https://youtube-mp36.p.rapidapi.com/dl"
    querystring = {"id": video_id}
    headers = {
        "x-rapidapi-host": "youtube-mp36.p.rapidapi.com",
        "x-rapidapi-key": RAPIDAPI_KEY,
    }

    try:
        response = requests.get(url, headers=headers, params=querystring)
        data = response.json()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
