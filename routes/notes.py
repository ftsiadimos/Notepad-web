import os

from flask import flash, redirect, render_template, request, url_for

from app import db
from models import Note

from . import main_bp


@main_bp.route('/')
def index():
    try:
        notes = Note.query.order_by(Note.updated_at.desc()).all()
        categories = sorted(list(set(note.category for note in notes if note.category)))
        return render_template('index.html', notes=notes, categories=categories)
    except Exception as e:
        flash(f'Error loading notes: {str(e)}', 'warning')
        return render_template('index.html', notes=[], categories=[])


@main_bp.route('/about')
def about():
    try:
        version_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'VERSION')
        with open(version_path, 'r') as f:
            version = f.read().strip()
    except Exception:
        version = 'dev'
    return render_template('about.html', version=version)


@main_bp.route('/note/new', methods=['GET', 'POST'])
def note_new():
    if request.method == 'POST':
        try:
            title = request.form.get('title', '').strip() or 'Untitled'
            content = request.form.get('content', '').strip()
            category = request.form.get('category', '').strip() or None

            if len(title) > 200:
                flash('Title is too long (max 200 characters)', 'warning')
                return render_template('note_form.html', note=None)

            note = Note(title=title, content=content, category=category)
            db.session.add(note)
            db.session.commit()
            flash('Note created successfully!', 'success')
            return redirect(url_for('main.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating note: {str(e)}', 'warning')
            return render_template('note_form.html', note=None)
    return render_template('note_form.html', note=None)


@main_bp.route('/note/<int:note_id>', methods=['GET', 'POST'])
def note_edit(note_id):
    try:
        note = Note.query.get_or_404(note_id)
        if request.method == 'POST':
            title = request.form.get('title', '').strip() or 'Untitled'
            content = request.form.get('content', '').strip()
            category = request.form.get('category', '').strip() or None

            if len(title) > 200:
                flash('Title is too long (max 200 characters)', 'warning')
                return render_template('note_form.html', note=note)

            note.title = title
            note.content = content
            note.category = category
            db.session.commit()
            flash('Note updated successfully!', 'success')
            return redirect(url_for('main.index'))
        return render_template('note_form.html', note=note)
    except Exception as e:
        flash(f'Error: {str(e)}', 'warning')
        return redirect(url_for('main.index'))


@main_bp.route('/note/<int:note_id>/delete', methods=['POST'])
def note_delete(note_id):
    try:
        note = Note.query.get_or_404(note_id)
        db.session.delete(note)
        db.session.commit()
        flash('Note deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting note: {str(e)}', 'warning')
    return redirect(url_for('main.index'))
