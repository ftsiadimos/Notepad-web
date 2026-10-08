from flask import Blueprint

main_bp = Blueprint('main', __name__)

# Sub-modules must be imported after main_bp is defined
from . import notes, settings, exports, ai, api  # noqa: E402, F401
