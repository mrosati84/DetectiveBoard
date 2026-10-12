from dotenv import load_dotenv

_ = load_dotenv()

import os
from typing import cast

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from detectiveboard.blueprints.auth import bp as auth_blueprint
from detectiveboard.blueprints.boards import bp as boards_blueprint
from detectiveboard.blueprints.cards import bp as cards_blueprint
from detectiveboard.blueprints.connections import (
    bp as connections_blueprint,
)
from detectiveboard.blueprints.notes import bp as notes_blueprint
from detectiveboard.blueprints.pages import bp as pages_blueprint
from detectiveboard.blueprints.share import bp as share_blueprint
from detectiveboard.config import BASE_DIR, load_config
from detectiveboard.errors import register_error_handlers
from detectiveboard.extensions import limiter


def create_app() -> Flask:
    app = Flask(
        __name__,
        static_folder=str(BASE_DIR / "static"),
        template_folder=str(BASE_DIR / "templates"),
    )
    # Railway's edge proxy rewrites Host; trust its X-Forwarded-Host/-Proto so
    # request.host and request.scheme reflect what the client asked for.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    load_config(app)
    limiter.init_app(app)
    os.makedirs(cast("str", app.config["UPLOAD_FOLDER"]), exist_ok=True)

    app.register_blueprint(pages_blueprint)
    app.register_blueprint(auth_blueprint)
    app.register_blueprint(boards_blueprint)
    app.register_blueprint(cards_blueprint)
    app.register_blueprint(notes_blueprint)
    app.register_blueprint(connections_blueprint)
    app.register_blueprint(share_blueprint)

    register_error_handlers(app)
    return app
