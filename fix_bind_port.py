try:
    from main import app
except Exception:
    from flask import Flask
    app = Flask(__name__)
    @app.get("/")
    def _health(): return "OK"
if __name__ == "__main__":
    import os
    app.run(host="0.0.0.0", port=int(os.getenv("PORT",8000)))
