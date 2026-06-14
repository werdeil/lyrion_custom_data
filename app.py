from flask import Flask

from config import Config
from routes.nowplaying import nowplaying_bp
from routes.custom import custom_bp
from services.database import get_stats


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    @app.route("/health", methods=["GET"])
    def healthcheck():
        return {"status": "ok"}, 200

    @app.route("/stats.json", methods=["GET"])
    def stats_json():
        stats = get_stats()
        json_text = app.response_class(
            response=app.json.dumps(stats, indent=2, ensure_ascii=False),
            status=200,
            mimetype="application/json",
        )
        return json_text

    # Register blueprints
    app.register_blueprint(nowplaying_bp)
    app.register_blueprint(custom_bp)

    return app

# 👇 AJOUT IMPORTANT
app = create_app()

if __name__ == "__main__":
    app.run(
        host=app.config["HOST"],
        port=app.config["PORT"],
    )
