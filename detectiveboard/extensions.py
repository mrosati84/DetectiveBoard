"""Flask extension singletons.

The limiter is constructed bare and initialized by the app factory via
``limiter.init_app(app)`` so that storage configuration is read from
``app.config["RATELIMIT_STORAGE_URI"]``.
"""

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
