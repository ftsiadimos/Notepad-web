from flask import jsonify

from models import Note

from . import main_bp


@main_bp.route('/debug/notes')
def debug_notes():
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


@main_bp.route('/api/notes/count', methods=['GET'])
def notes_count():
    try:
        total_notes = Note.query.count()
        return jsonify({'total_notes': total_notes})
    except Exception as e:
        return jsonify({'error': f'Failed to count notes: {str(e)}'}), 500
