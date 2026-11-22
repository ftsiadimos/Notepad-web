import json
import os
import time

from flask import flash, jsonify, redirect, render_template, request, send_file, url_for

from app import db
from models import AppSetting, Category, Note
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
            categories = Category.query.all()
            return render_template(
                'settings.html',
                ollama_url=ollama_url,
                ollama_model=ollama_model,
                available_models=available_models,
                model_fetch_error=model_fetch_error,
                default_url=DEFAULT_OLLAMA_URL,
                default_model=DEFAULT_OLLAMA_MODEL,
                current_theme=current_theme,
                categories=categories,
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
    categories = Category.query.all()

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
        categories=categories,
    )


@main_bp.route('/api/categories', methods=['GET'])
def api_get_categories():
    try:
        categories = Category.query.all()
        return jsonify([cat.to_dict() for cat in categories])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@main_bp.route('/api/categories', methods=['POST'])
def api_create_category():
    try:
        data = request.get_json() or {}
        name = data.get('name', '').strip()
        color = data.get('color', '#3498db').strip()

        if not name:
            return jsonify({'error': 'Category name is required'}), 400

        if len(name) > 100:
            return jsonify({'error': 'Category name is too long (max 100 characters)'}), 400

        if Category.query.filter_by(name=name).first():
            return jsonify({'error': 'Category already exists'}), 409

        category = Category(name=name, color=color)
        db.session.add(category)
        db.session.commit()
        return jsonify(category.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@main_bp.route('/api/categories/<int:category_id>', methods=['GET'])
def api_get_category(category_id):
    try:
        category = Category.query.get_or_404(category_id)
        return jsonify(category.to_dict())
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@main_bp.route('/api/categories/<int:category_id>', methods=['PUT'])
def api_update_category(category_id):
    try:
        category = Category.query.get_or_404(category_id)
        data = request.get_json() or {}
        
        name = data.get('name', '').strip()
        color = data.get('color', '').strip()

        if name and len(name) > 100:
            return jsonify({'error': 'Category name is too long (max 100 characters)'}), 400

        if name and name != category.name:
            if Category.query.filter_by(name=name).first():
                return jsonify({'error': 'Category name already exists'}), 409
            category.name = name

        if color:
            category.color = color

        db.session.commit()
        return jsonify(category.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@main_bp.route('/api/categories/<int:category_id>', methods=['DELETE'])
def api_delete_category(category_id):
    try:
        category = Category.query.get_or_404(category_id)
        db.session.delete(category)
        db.session.commit()
        return jsonify({'message': 'Category deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@main_bp.route('/settings/export')
def settings_export():
    """Export all notes, categories, and settings as a JSON backup file."""
    try:
        notes = Note.query.all()
        categories = Category.query.all()
        settings = AppSetting.query.all()

        backup_data = {
            'notes': [note.to_dict() for note in notes],
            'categories': [cat.to_dict() for cat in categories],
            'settings': [{'key': s.key, 'value': s.value} for s in settings],
            'exported_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
        }

        json_str = json.dumps(backup_data, indent=2)
        from io import BytesIO
        buffer = BytesIO(json_str.encode('utf-8'))
        buffer.seek(0)

        return send_file(
            buffer,
            mimetype='application/json',
            as_attachment=True,
            download_name=f'notepad-backup-{time.strftime("%Y-%m-%d")}.json',
        )
    except Exception as e:
        flash(f'Error exporting notes: {str(e)}', 'error')
        return redirect(url_for('main.settings'))


@main_bp.route('/settings/import', methods=['POST'])
def settings_import():
    """Import notes, categories, and settings from an uploaded JSON backup file."""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided.'}), 400

        file = request.files['file']
        if not file or not file.filename or not file.filename.endswith('.json'):
            return jsonify({'error': 'Please upload a valid JSON backup file.'}), 400

        try:
            backup_data = json.load(file)
        except json.JSONDecodeError:
            return jsonify({'error': 'Invalid JSON file.'}), 400

        count_notes = 0
        count_categories = 0
        count_settings = 0

        # Import categories
        for cat_data in backup_data.get('categories', []):
            try:
                name = cat_data.get('name', '').strip()
                color = cat_data.get('color', '#3498db')
                if not name:
                    continue
                existing = Category.query.filter_by(name=name).first()
                if existing:
                    existing.color = color
                    count_categories += 1
                else:
                    category = Category(name=name, color=color)
                    db.session.add(category)
                    count_categories += 1
            except Exception:
                pass

        # Import notes
        for note_data in backup_data.get('notes', []):
            try:
                title = note_data.get('title', 'Untitled').strip() or 'Untitled'
                content = note_data.get('content', '').strip()
                category = note_data.get('category', None)
                note = Note(title=title, content=content, category=category)
                db.session.add(note)
                count_notes += 1
            except Exception:
                pass

        # Import settings
        for setting_data in backup_data.get('settings', []):
            try:
                key = setting_data.get('key', '').strip()
                value = setting_data.get('value', '')
                if key:
                    set_setting_value(key, value)
                    count_settings += 1
            except Exception:
                pass

        db.session.commit()
        message = (
            f'Imported {count_notes} note{"s" if count_notes != 1 else ""}, '
            f'{count_categories} category/categories, '
            f'and {count_settings} setting(s) successfully!'
        )
        flash(message, 'success')
        return jsonify({'success': True, 'message': message})
    except Exception as e:
        db.session.rollback()
        error_msg = f'Error importing notes: {str(e)}'
        flash(error_msg, 'error')
        return jsonify({'error': error_msg}), 500
