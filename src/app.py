"""
Application entry point.

Each analytics domain is a blueprint registered here. Adding a module means
adding a package under src/modules/ and one register_blueprint() line.
"""

from flask import Flask
from flask_cors import CORS

from config.settings import CORS_ORIGINS, DEBUG, HOST, PORT
from src.modules.diversity.routes import diversity_bp


def create_app():
    app = Flask(__name__)
    CORS(app, resources={r"/*": {"origins": CORS_ORIGINS}})

    app.register_blueprint(diversity_bp)
    # app.register_blueprint(demographics_bp)
    # app.register_blueprint(summary_bp)

    @app.route("/health", methods=["GET"])
    def health():
        return {"status": "ok"}

    return app


if __name__ == "__main__":
    create_app().run(host=HOST, port=PORT, debug=DEBUG)
