from flask import Flask, jsonify
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from config import Config
from routes.analysis import analysis_bp
from routes.health import health_bp
from routes.parse import parse_bp
from routes.projects import projects_bp


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    CORS(app, origins=app.config["CORS_ORIGINS"])

    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(parse_bp, url_prefix="/api/parse")
    app.register_blueprint(analysis_bp, url_prefix="/api/analysis")
    app.register_blueprint(projects_bp, url_prefix="/api/projects")

    @app.errorhandler(HTTPException)
    def handle_http_error(err):
        return jsonify(error=err.name, message=err.description), err.code

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
