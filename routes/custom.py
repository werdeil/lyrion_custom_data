from flask import Blueprint, current_app, send_from_directory

custom_bp = Blueprint("custom", __name__)


@custom_bp.route("/files/")
@custom_bp.route("/files/<path:filepath>")
def serve_file(filepath=""):
    """Serve static files from the custom data directory."""
    base_dir = current_app.config["CUSTOM_DATA_DIR"]
    return send_from_directory(base_dir, filepath)
