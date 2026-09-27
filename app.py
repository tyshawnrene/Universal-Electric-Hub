from flask import Flask, abort, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from backend.config import Config
from backend.routes.analysis import analysis_bp
from backend.routes.health import health_bp
from backend.routes.parse import parse_bp
from backend.routes.projects import projects_bp
import os


def create_app(config_class=Config):
    app = Flask(__name__, static_folder=None)
    app.config.from_object(config_class)
    CORS(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})

    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(parse_bp, url_prefix="/api/parse")
    app.register_blueprint(analysis_bp, url_prefix="/api/analysis")
    app.register_blueprint(projects_bp, url_prefix="/api/projects")

    @app.errorhandler(HTTPException)
    def handle_http_error(err):
        return jsonify(error=err.name, message=err.description), err.code

    # Serve the built React app (frontend/dist) so one Flask process runs everything.
    # During development, use `npm run dev` instead; Vite proxies /api to this server.
    dist = config_class.FRONTEND_DIST

    @app.get("/", defaults={"path": ""})
    @app.get("/<path:path>")
    def frontend(path):
        if path.startswith("api/"):
            abort(404)
        if not (dist / "index.html").exists():
            abort(404, description="Frontend not built. Run `npm run build` in frontend/, or use `npm run dev`.")
        if path and (dist / path).is_file():
            return send_from_directory(dist, path)
        return send_from_directory(dist, "index.html")

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
