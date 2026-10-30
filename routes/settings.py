import os

from flask import flash, redirect, render_template, request, url_for

from app import db
from utils.helpers import (
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_OLLAMA_URL,
    fetch_ollama_models,
    get_setting_value,
    set_setting_value,
)

from . import main_bp


@main_bp.route('/settings', methods=['GET', 'POST'])
def settings():
    model_fetch_error = None

    if request.method == 'POST':
        ollama_url = request.form.get('ollama_url', '').strip()
        ollama_model = request.form.get('ollama_model', '').strip()
        theme = request.form.get('theme', 'light').strip()
        ai_instructions = request.form.get('ai_instructions', '').strip()

        set_setting_value('theme', theme)
        set_setting_value('ai_instructions', ai_instructions)

        if ollama_url and not (ollama_url.startswith('http://') or ollama_url.startswith('https://')):
            flash('Ollama API URL must start with http:// or https://', 'warning')
            available_models = [ollama_model] if ollama_model else []
            current_theme = get_setting_value('theme', 'light')
            return render_template(
                'settings.html',
                ollama_url=ollama_url,
                ollama_model=ollama_model,
                available_models=available_models,
                model_fetch_error=model_fetch_error,
                default_url=DEFAULT_OLLAMA_URL,
                default_model=DEFAULT_OLLAMA_MODEL,
                current_theme=current_theme,
            )

        try:
            set_setting_value('ollama_api_url', ollama_url)
            set_setting_value('ollama_model', ollama_model)
            db.session.commit()
            flash('Settings saved successfully!', 'success')
            return redirect(url_for('main.settings'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error saving settings: {str(e)}', 'warning')

    ollama_url = get_setting_value('ollama_api_url', os.environ.get('OLLAMA_API_URL', DEFAULT_OLLAMA_URL))
    ollama_model = get_setting_value('ollama_model', os.environ.get('OLLAMA_MODEL', DEFAULT_OLLAMA_MODEL))
    current_theme = get_setting_value('theme', 'light')
    ai_instructions = get_setting_value('ai_instructions', '')

    available_models, model_fetch_error = fetch_ollama_models(ollama_url)
    if ollama_model and ollama_model not in available_models:
        available_models.insert(0, ollama_model)
    if not available_models:
        available_models = [DEFAULT_OLLAMA_MODEL]

    return render_template(
        'settings.html',
        ollama_url=ollama_url,
        ollama_model=ollama_model,
        available_models=available_models,
        model_fetch_error=model_fetch_error,
        default_url=DEFAULT_OLLAMA_URL,
        default_model=DEFAULT_OLLAMA_MODEL,
        current_theme=current_theme,
        ai_instructions=ai_instructions,
    )
