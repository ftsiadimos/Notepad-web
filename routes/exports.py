from flask import flash, jsonify, redirect, request, send_file, url_for

from models import Note
from utils.pdf import notes_to_pdf
from utils.word import notes_to_docx

from . import main_bp


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
            download_name='notepad-notes.pdf',
        )
    except Exception as e:
        flash(f'Error exporting PDF: {str(e)}', 'warning')
        return redirect(url_for('main.index'))


@main_bp.route('/export/pdf/selected', methods=['POST'])
def export_selected_pdf():
    try:
        data = request.get_json(silent=True) or {}
        note_ids = data.get('note_ids', []) or []
        note_ids = [int(nid) for nid in note_ids if nid]

        if not note_ids:
            flash('No notes selected for export.', 'warning')
            return jsonify({'error': 'No notes selected'}), 400

        notes = Note.query.filter(Note.id.in_(note_ids)).order_by(Note.updated_at.desc()).all()

        if not notes:
            flash('No valid notes found for export.', 'warning')
            return jsonify({'error': 'No valid notes found'}), 404

        pdf_buffer = notes_to_pdf(notes)
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='notepad-notes-selected.pdf',
        )
    except Exception as e:
        flash(f'Error exporting PDF: {str(e)}', 'warning')
        return jsonify({'error': str(e)}), 500


@main_bp.route('/export/pdf/<int:note_id>')
def export_single_pdf(note_id):
    try:
        note = Note.query.get_or_404(note_id)
        pdf_buffer = notes_to_pdf([note])
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'notepad-note-{note.id}.pdf',
        )
    except Exception as e:
        flash(f'Error exporting PDF: {str(e)}', 'warning')
        return redirect(url_for('main.index'))


@main_bp.route('/export/docx')
def export_docx():
    try:
        notes = Note.query.order_by(Note.updated_at.desc()).all()
        if not notes:
            flash('No notes to export.', 'warning')
            return redirect(url_for('main.index'))
        docx_buffer = notes_to_docx(notes)
        return send_file(
            docx_buffer,
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            as_attachment=True,
            download_name='notepad-notes.docx',
        )
    except Exception as e:
        flash(f'Error exporting Word: {str(e)}', 'warning')
        return redirect(url_for('main.index'))


@main_bp.route('/export/docx/selected', methods=['POST'])
def export_selected_docx():
    try:
        data = request.get_json(silent=True) or {}
        note_ids = data.get('note_ids', []) or []
        note_ids = [int(nid) for nid in note_ids if nid]

        if not note_ids:
            flash('No notes selected for export.', 'warning')
            return jsonify({'error': 'No notes selected'}), 400

        notes = Note.query.filter(Note.id.in_(note_ids)).order_by(Note.updated_at.desc()).all()

        if not notes:
            flash('No valid notes found for export.', 'warning')
            return jsonify({'error': 'No valid notes found'}), 404

        docx_buffer = notes_to_docx(notes)
        return send_file(
            docx_buffer,
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            as_attachment=True,
            download_name='notepad-notes-selected.docx',
        )
    except Exception as e:
        flash(f'Error exporting Word: {str(e)}', 'warning')
        return jsonify({'error': str(e)}), 500


@main_bp.route('/export/docx/<int:note_id>')
def export_single_docx(note_id):
    try:
        note = Note.query.get_or_404(note_id)
        docx_buffer = notes_to_docx([note])
        return send_file(
            docx_buffer,
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            as_attachment=True,
            download_name=f'notepad-note-{note.id}.docx',
        )
    except Exception as e:
        flash(f'Error exporting Word: {str(e)}', 'warning')
        return redirect(url_for('main.index'))
