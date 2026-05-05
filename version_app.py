from flask import Flask, jsonify


VERSION = "1.0.2"
RELEASE_DATE = "2025-05-05"

app = Flask(__name__)


@app.get("/")
def index():
    return jsonify(
        {
            "version": VERSION,
            "release_date": RELEASE_DATE,
        }
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
