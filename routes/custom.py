import os
import subprocess
from functools import wraps

from flask import Blueprint, current_app, render_template, request, abort, send_from_directory

custom_bp = Blueprint("custom", __name__)


def require_token(f):
    """Decorator that checks the ?token= query parameter."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.args.get("token")
        if token != current_app.config["CUSTOM_TOKEN"]:
            abort(403)
        return f(*args, **kwargs)
    return decorated


@custom_bp.route("/run-script")
@require_token
def run_script():
    """Launch the custom stats shell script (non-blocking)."""
    try:
        script = current_app.config["CUSTOM_SCRIPT_PATH"]
        subprocess.Popen([script])
        return "Script launched", 200
    except Exception as e:
        return str(e), 500


@custom_bp.route("/run")
@require_token
def run():
    """Serve the HTML page that triggers /run-script via fetch() then auto-closes."""
    return render_template(
        "run_script.html",
        token=current_app.config["CUSTOM_TOKEN"],
    )


@custom_bp.route("/files/")
@custom_bp.route("/files/<path:filepath>")
def serve_file(filepath=""):
    """Serve static files from the custom data directory."""
    base_dir = current_app.config["CUSTOM_DATA_DIR"]
    return send_from_directory(base_dir, filepath)
