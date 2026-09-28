from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from app import db
from models import Note
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit
import io
import os
import re
from html.parser import HTMLParser

main_bp = Blueprint('main', __name__)

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
        # Fallback to regex if parsing fails
        return re.sub(r'<[^>]+>', '', html_text).strip()

def notes_to_pdf(notes_list):
    """Convert a list of Note objects to a PDF byte stream."""
    try:
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter
        y_position = height - 50

        # Title
        c.setFont("Helvetica-Bold", 20)
        c.drawString(50, y_position, "Notepad Export")
        y_position -= 40

        for note in notes_list:
            # Check if we need a new page
            if y_position < 100:
                c.showPage()
                y_position = height - 50
                c.setFont("Helvetica-Bold", 20)
                c.drawString(50, y_position, "Notepad Export")
                y_position -= 40

            # Note title
            c.setFont("Helvetica-Bold", 14)
            title_text = note.title or "Untitled"
            c.drawString(50, y_position, f"Title: {title_text}")
            y_position -= 25

            # Note date
            c.setFont("Helvetica-Oblique", 10)
            created = note.created_at.strftime('%Y-%m-%d %H:%M') if note.created_at else 'N/A'
            updated = note.updated_at.strftime('%Y-%m-%d %H:%M') if note.updated_at else 'N/A'
            c.drawString(50, y_position, f"Created: {created} | Updated: {updated}")
            y_position -= 25

            # Note content - word wrap (strip HTML tags first)
            content_text = strip_html(note.content) if note.content else "(No content)"
            c.setFont("Helvetica", 11)
            lines = simpleSplit(content_text, "Helvetica", 11, width - 100)
            for line in lines:
                if y_position < 50:
                    c.showPage()
                    y_position = height - 50
                c.drawString(50, y_position, line)
                y_position -= 15

            y_position -= 20
            c.line(50, y_position + 10, width - 50, y_position + 10)
            y_position -= 30

        c.save()
        buffer.seek(0)
        return buffer
    except Exception as e:
        print(f"Error generating PDF: {e}")
        raise

@main_bp.route('/')
def index():
    try:
        notes = Note.query.order_by(Note.updated_at.desc()).all()
        return render_template('index.html', notes=notes)
    except Exception as e:
        flash(f'Error loading notes: {str(e)}', 'warning')
        return render_template('index.html', notes=[])

@main_bp.route('/note/new', methods=['GET', 'POST'])
def note_new():
    if request.method == 'POST':
        try:
            title = request.form.get('title', '').strip() or 'Untitled'
            content = request.form.get('content', '').strip()
            
            # Validate title length
            if len(title) > 200:
                flash('Title is too long (max 200 characters)', 'warning')
                return render_template('note_form.html', note=None)
            
            note = Note(title=title, content=content)
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
            
            # Validate title length
            if len(title) > 200:
                flash('Title is too long (max 200 characters)', 'warning')
                return render_template('note_form.html', note=note)
            
            note.title = title
            note.content = content
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

@main_bp.route('/export/pdf')
def export_pdf():
    try:
        notes = Note.query.order_by(Note.updated_at.desc()).all()
        if not notes:
            flash('No notes to export.', 'warning')
            return redirect(url_for('main.index'))
        pdf_buffer = notes_to_pdf(notes)
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='notepad-notes.pdf'
        )
    except Exception as e:
        flash(f'Error exporting PDF: {str(e)}', 'warning')
        return redirect(url_for('main.index'))

@main_bp.route('/export/pdf/<int:note_id>')
def export_single_pdf(note_id):
    try:
        note = Note.query.get_or_404(note_id)
        pdf_buffer = notes_to_pdf([note])
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'notepad-note-{note.id}.pdf'
        )
    except Exception as e:
        flash(f'Error exporting PDF: {str(e)}', 'warning')
        return redirect(url_for('main.index'))

@main_bp.route('/debug/notes')
def debug_notes():
    """Debug endpoint to check database content"""
    notes = Note.query.all()
    data = []
    for note in notes:
        data.append({
            'id': note.id,
            'title': note.title,
            'content_length': len(note.content) if note.content else 0,
            'content_preview': note.content[:100] if note.content else '(empty)',
            'content_raw': note.content,
        })
    return {'notes': data}
