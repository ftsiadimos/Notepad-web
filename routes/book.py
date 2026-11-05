from flask import render_template, request
from models import Note

from . import main_bp


@main_bp.route('/book')
def book_view():
    """Book-like reading view that displays all notes as pages in a book."""
    try:
        notes = Note.query.order_by(Note.updated_at.desc()).all()
        return render_template('book.html', notes=notes)
    except Exception as e:
        return render_template('book.html', notes=[], error=str(e))
