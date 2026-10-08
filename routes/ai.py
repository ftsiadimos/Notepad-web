import json
import os
import re
from urllib import error as urllib_error
from urllib import request as urllib_request

from flask import jsonify, request

from utils.helpers import DEFAULT_OLLAMA_MODEL, DEFAULT_OLLAMA_URL, get_setting_value

from . import main_bp


@main_bp.route('/ai/chat', methods=['POST'])
def ai_chat():
    data = request.get_json(silent=True) or {}
    user_prompt = (data.get('prompt') or '').strip()
    note_content_html = (data.get('content_html') or '').strip()
    note_content_text = (data.get('content_text') or '').strip()

    if not user_prompt:
        return jsonify({'error': 'Prompt is required.'}), 400

    ollama_url = get_setting_value('ollama_api_url', os.environ.get('OLLAMA_API_URL', DEFAULT_OLLAMA_URL)).rstrip('/')
    ollama_model = get_setting_value('ollama_model', os.environ.get('OLLAMA_MODEL', DEFAULT_OLLAMA_MODEL))
    api_url = f'{ollama_url}/api/generate'

    system_context = (
        'You are an assistant that edits existing notes. '
        'Read the current note content and apply the user request as recommendations and improvements. '
        'Return ONLY HTML that should replace the existing note content. '
        'Preserve the original formatting style as much as possible (font sizes, headings, lists, emphasis, spacing). '
        'Do not wrap the answer in markdown fences. Do not include explanations or commentary.'
    )
    full_prompt = (
        f'{system_context}\n\n'
        f'Current note content (HTML):\n{note_content_html if note_content_html else "(empty)"}\n\n'
        f'Current note content (plain text):\n{note_content_text if note_content_text else "(empty)"}\n\n'
        f'User request:\n{user_prompt}'
    )

    payload = {
        'model': ollama_model,
        'prompt': full_prompt,
        'stream': False,
    }

    try:
        req = urllib_request.Request(
            api_url,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        with urllib_request.urlopen(req, timeout=45) as response:
            raw = response.read().decode('utf-8')
            result = json.loads(raw)
            ai_html = (result.get('response') or '').strip()
            if ai_html.startswith('```'):
                ai_html = re.sub(r'^```[a-zA-Z]*\n?', '', ai_html)
                ai_html = re.sub(r'\n?```$', '', ai_html).strip()

            if not ai_html:
                return jsonify({'error': 'Ollama returned an empty response.'}), 502
            return jsonify({'response': ai_html})
    except urllib_error.HTTPError as e:
        try:
            details = e.read().decode('utf-8')
        except Exception:
            details = str(e)
        return jsonify({'error': f'Ollama HTTP error: {e.code}. {details}'}), 502
    except urllib_error.URLError as e:
        return jsonify({'error': f'Could not reach Ollama API at {ollama_url}. {e.reason}'}), 502
    except Exception as e:
        return jsonify({'error': f'AI request failed: {str(e)}'}), 500
