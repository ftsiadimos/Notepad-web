import json
import re
from html.parser import HTMLParser
from urllib import request as urllib_request

from app import db
from models import AppSetting

DEFAULT_OLLAMA_URL = 'http://localhost:11434'
DEFAULT_OLLAMA_MODEL = 'llama3.2'


def get_setting_value(key, default=''):
    setting = AppSetting.query.filter_by(key=key).first()
    if setting and setting.value:
        return setting.value.strip()
    return default


def set_setting_value(key, value):
    setting = AppSetting.query.filter_by(key=key).first()
    if setting is None:
        setting = AppSetting(key=key, value=value)
        db.session.add(setting)
    else:
        setting.value = value


def fetch_ollama_models(ollama_url):
    """Fetch available model names from Ollama /api/tags."""
    if not ollama_url:
        return [], 'Ollama URL is empty.'

    try:
        api_url = f"{ollama_url.rstrip('/')}/api/tags"
        with urllib_request.urlopen(api_url, timeout=8) as response:
            raw = response.read().decode('utf-8')
            payload = json.loads(raw)
            models = payload.get('models') or []

            names = []
            for model in models:
                name = (model.get('name') or '').strip()
                if name and name not in names:
                    names.append(name)
            return names, None
    except Exception as e:
        return [], str(e)


class HTMLStripper(HTMLParser):
    """Remove HTML tags from text."""
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.text = []

    def handle_data(self, d):
        self.text.append(d)

    def get_data(self):
        return ''.join(self.text)


def strip_html(html_text):
    """Strip HTML tags from text."""
    if not html_text:
        return ""
    try:
        stripper = HTMLStripper()
        stripper.feed(html_text)
        return stripper.get_data().strip()
    except Exception:
        return re.sub(r'<[^>]+>', '', html_text).strip()
