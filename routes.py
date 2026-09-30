from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, jsonify
from app import db
from models import Note, AppSetting
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    HRFlowable,
    ListFlowable,
    ListItem,
    XPreformatted,
)
import io
import os
import re
import json
import importlib
from urllib import request as urllib_request
from urllib import error as urllib_error
from html.parser import HTMLParser
from html import unescape
from xml.sax.saxutils import escape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY

main_bp = Blueprint('main', __name__)

DEFAULT_OLLAMA_URL = 'http://localhost:11434'
DEFAULT_OLLAMA_MODEL = 'llama3.2'

PDF_ICON_RE = re.compile(r'[\U0001F1E6-\U0001F1FF\U0001F300-\U0001FAFF\u2600-\u27BF\ufe0f]')


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
        # Fallback to regex if parsing fails
        return re.sub(r'<[^>]+>', '', html_text).strip()


def strip_icons_for_pdf(text):
    """Normalize punctuation and remove emoji/icon glyphs for cleaner PDF output."""
    if not text:
        return ''

    # Normalize dash variants that can render as missing glyphs in some PDF viewers/fonts.
    normalized = (
        text
        .replace('\u2011', '-')  # non-breaking hyphen
        .replace('\u2010', '-')  # hyphen
        .replace('\u2012', '-')  # figure dash
        .replace('\u2013', '-')  # en dash
        .replace('\u2014', '-')  # em dash
        .replace('\u2212', '-')  # minus sign
    )

    return PDF_ICON_RE.sub('', normalized)


def get_pdf_font_names():
    """Return a font set with Unicode support when available."""
    default_fonts = {
        'regular': 'Helvetica',
        'bold': 'Helvetica-Bold',
        'italic': 'Helvetica-Oblique',
        'bold_italic': 'Helvetica-BoldOblique',
        'mono': 'Courier',
        'family': 'Helvetica',
    }

    font_candidates = [
        {
            'prefix': 'DejaVuSans',
            'regular': '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            'bold': '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
            'italic': '/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf',
            'bold_italic': '/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf',
        },
        {
            'prefix': 'LiberationSans',
            'regular': '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
            'bold': '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
            'italic': '/usr/share/fonts/truetype/liberation/LiberationSans-Italic.ttf',
            'bold_italic': '/usr/share/fonts/truetype/liberation/LiberationSans-BoldItalic.ttf',
        },
    ]

    for candidate in font_candidates:
        if not os.path.exists(candidate['regular']):
            continue

        try:
            regular_name = f"{candidate['prefix']}-Regular"
            bold_name = f"{candidate['prefix']}-Bold"
            italic_name = f"{candidate['prefix']}-Italic"
            bold_italic_name = f"{candidate['prefix']}-BoldItalic"

            registered = set(pdfmetrics.getRegisteredFontNames())
            if regular_name not in registered:
                pdfmetrics.registerFont(TTFont(regular_name, candidate['regular']))
            if os.path.exists(candidate['bold']) and bold_name not in registered:
                pdfmetrics.registerFont(TTFont(bold_name, candidate['bold']))
            if os.path.exists(candidate['italic']) and italic_name not in registered:
                pdfmetrics.registerFont(TTFont(italic_name, candidate['italic']))
            if os.path.exists(candidate['bold_italic']) and bold_italic_name not in registered:
                pdfmetrics.registerFont(TTFont(bold_italic_name, candidate['bold_italic']))

            mono_name = 'Courier'
            mono_path = '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'
            if os.path.exists(mono_path):
                mono_name = f"{candidate['prefix']}-Mono"
                if mono_name not in set(pdfmetrics.getRegisteredFontNames()):
                    pdfmetrics.registerFont(TTFont(mono_name, mono_path))

            pdfmetrics.registerFontFamily(
                candidate['prefix'],
                normal=regular_name,
                bold=bold_name,
                italic=italic_name,
                boldItalic=bold_italic_name,
            )

            return {
                'regular': regular_name,
                'bold': bold_name,
                'italic': italic_name,
                'bold_italic': bold_italic_name,
                'mono': mono_name,
                'family': candidate['prefix'],
            }
        except Exception:
            continue

    return default_fonts


def inline_html_to_reportlab(node, tag_type, string_type, fonts):
    """Convert inline HTML nodes to ReportLab paragraph markup."""
    if isinstance(node, string_type):
        return escape(strip_icons_for_pdf(str(node)))

    if not isinstance(node, tag_type):
        return ''

    tag_name = node.name.lower()
    children = ''.join(inline_html_to_reportlab(child, tag_type, string_type, fonts) for child in node.children)

    if tag_name in ('strong', 'b'):
        return f'<font name="{fonts["bold"]}">{children}</font>'
    if tag_name in ('em', 'i'):
        return f'<font name="{fonts["italic"]}">{children}</font>'
    if tag_name == 'u':
        return f'<u>{children}</u>'
    if tag_name in ('s', 'strike', 'del'):
        return children
    if tag_name == 'br':
        return '<br/>'
    if tag_name == 'code':
        return f'<font name="{fonts["mono"]}">{children}</font>'
    if tag_name == 'a':
        href = (node.get('href') or '').strip()
        if href:
            return f'{children} ({escape(href)})'
        return children

    # span/div/unknown tags: keep content
    return children


def quill_indent_level(class_list):
    """Extract ql-indent-N level from class list."""
    for class_name in class_list or []:
        match = re.match(r'ql-indent-(\d+)', class_name)
        if match:
            try:
                return int(match.group(1))
            except Exception:
                return 0
    return 0


def li_markup_without_nested_lists(li_node, tag_type, string_type, fonts):
    """Get list-item inline markup while ignoring nested list blocks."""
    parts = []
    for child in li_node.children:
        if isinstance(child, tag_type) and child.name and child.name.lower() in ('ul', 'ol'):
            continue
        parts.append(inline_html_to_reportlab(child, tag_type, string_type, fonts))
    return ''.join(parts).strip()


def alignment_from_classes(class_list):
    classes = class_list or []
    if 'ql-align-center' in classes:
        return TA_CENTER
    if 'ql-align-right' in classes:
        return TA_RIGHT
    if 'ql-align-justify' in classes:
        return TA_JUSTIFY
    return TA_LEFT


def html_to_flowables(html_text, styles, fonts):
    """Convert note HTML to flowables while preserving common formatting."""
    body_style = styles['BodyText']
    heading_styles = {
        'h1': styles['Heading1'],
        'h2': styles['Heading2'],
        'h3': styles['Heading3'],
        'h4': ParagraphStyle('H4', parent=styles['Heading3'], fontSize=12, spaceAfter=6),
        'h5': ParagraphStyle('H5', parent=styles['Heading3'], fontSize=11, spaceAfter=6),
        'h6': ParagraphStyle('H6', parent=styles['Heading3'], fontSize=10, spaceAfter=6),
    }
    blockquote_style = ParagraphStyle(
        'BlockQuote',
        parent=body_style,
        leftIndent=18,
        textColor=colors.HexColor('#555555'),
        italic=True,
        spaceBefore=4,
        spaceAfter=6,
    )
    code_style = ParagraphStyle(
        'CodeBlock',
        parent=body_style,
        fontName=fonts['mono'],
        fontSize=9,
        leading=11,
        leftIndent=10,
        backColor=colors.HexColor('#f4f4f4'),
        borderPadding=6,
        spaceBefore=4,
        spaceAfter=8,
    )

    if not html_text:
        return [Paragraph('(No content)', body_style)]

    try:
        bs4 = importlib.import_module('bs4')
        BeautifulSoup = bs4.BeautifulSoup
        NavigableString = bs4.NavigableString
        Tag = bs4.Tag
    except Exception:
        BeautifulSoup = None

    if BeautifulSoup is None:
        # Fallback if bs4 is unavailable: export plain text.
        return [Paragraph(escape(strip_html(html_text) or '(No content)'), body_style)]

    soup = BeautifulSoup(html_text, 'html.parser')
    container = soup.body if soup.body else soup
    flowables = []

    for node in container.children:
        if isinstance(node, NavigableString):
            text = str(node).strip()
            if text:
                flowables.append(Paragraph(escape(text), body_style))
                flowables.append(Spacer(1, 4))
            continue

        if not isinstance(node, Tag):
            continue

        name = node.name.lower()

        if name in heading_styles:
            markup = inline_html_to_reportlab(node, Tag, NavigableString, fonts).strip() or '&nbsp;'
            style = ParagraphStyle(
                f'{name}_aligned',
                parent=heading_styles[name],
                alignment=alignment_from_classes(node.get('class') or []),
                fontName=fonts['bold'],
            )
            flowables.append(Paragraph(markup, style))
            flowables.append(Spacer(1, 4))
            continue

        if name in ('p', 'div'):
            markup = inline_html_to_reportlab(node, Tag, NavigableString, fonts).strip()
            paragraph_style = ParagraphStyle(
                'BodyAligned',
                parent=body_style,
                alignment=alignment_from_classes(node.get('class') or []),
                fontName=fonts['regular'],
                leading=14,
            )
            if markup:
                flowables.append(Paragraph(markup, paragraph_style))
            else:
                flowables.append(Spacer(1, 8))
            flowables.append(Spacer(1, 4))
            continue

        if name in ('ul', 'ol'):
            ordered_counters = {}
            for li in node.find_all('li', recursive=False):
                indent_level = quill_indent_level(li.get('class') or [])
                list_kind = (li.get('data-list') or ('bullet' if name == 'ul' else 'ordered')).lower()

                # Reset deeper counters when indentation moves up.
                for level_key in list(ordered_counters.keys()):
                    if level_key > indent_level:
                        ordered_counters.pop(level_key, None)

                if list_kind == 'ordered':
                    ordered_counters[indent_level] = ordered_counters.get(indent_level, 0) + 1
                    bullet_prefix = f"{ordered_counters[indent_level]}."
                elif list_kind == 'checked':
                    bullet_prefix = '[x]'
                elif list_kind == 'unchecked':
                    bullet_prefix = '[ ]'
                else:
                    bullet_prefix = '•'

                item_markup = li_markup_without_nested_lists(li, Tag, NavigableString, fonts) or '&nbsp;'
                list_item_style = ParagraphStyle(
                    f'ListItem_{indent_level}_{list_kind}',
                    parent=body_style,
                    leftIndent=18 + (indent_level * 18),
                    firstLineIndent=-12,
                    spaceBefore=0,
                    spaceAfter=1,
                    leading=14,
                    fontName=fonts['regular'],
                )
                flowables.append(Paragraph(f'{bullet_prefix} {item_markup}', list_item_style))

                # Handle true nested list nodes if they exist in HTML.
                for child in li.children:
                    if isinstance(child, Tag) and child.name and child.name.lower() in ('ul', 'ol'):
                        nested_html = str(child)
                        flowables.extend(html_to_flowables(nested_html, styles, fonts))

                flowables.append(Spacer(1, 2))
            continue

        if name == 'blockquote':
            markup = inline_html_to_reportlab(node, Tag, NavigableString, fonts).strip()
            if markup:
                flowables.append(Paragraph(markup, blockquote_style))
                flowables.append(Spacer(1, 4))
            continue

        if name == 'pre':
            code_text = strip_icons_for_pdf(unescape(node.get_text('\n'))).rstrip() or '(empty code block)'
            flowables.append(XPreformatted(code_text, code_style))
            flowables.append(Spacer(1, 4))
            continue

        # Generic fallback for other block tags.
        markup = inline_html_to_reportlab(node, Tag, NavigableString, fonts).strip()
        if markup:
            flowables.append(Paragraph(markup, body_style))
            flowables.append(Spacer(1, 4))

    if not flowables:
        flowables.append(Paragraph('(No content)', body_style))
    return flowables

def notes_to_pdf(notes_list):
    """Convert a list of Note objects to a PDF byte stream."""
    try:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=45,
            rightMargin=45,
            topMargin=45,
            bottomMargin=45,
            title='Notepad Export',
        )
        styles = getSampleStyleSheet()
        fonts = get_pdf_font_names()
        styles['Normal'].fontName = fonts['regular']
        styles['BodyText'].fontName = fonts['regular']
        styles['Heading1'].fontName = fonts['bold']
        styles['Heading2'].fontName = fonts['bold']
        styles['Heading3'].fontName = fonts['bold']
        story = []

        note_title_style = ParagraphStyle(
            'NoteTitle',
            parent=styles['Heading2'],
            fontName=fonts['bold'],
            alignment=TA_CENTER,
            fontSize=18,
            leading=21,
            spaceBefore=8,
            spaceAfter=26,
        )

        for index, note in enumerate(notes_list):
            title_text = escape(strip_icons_for_pdf(note.title or 'Untitled'))

            story.append(Paragraph(title_text, note_title_style))
            story.extend(html_to_flowables(note.content, styles, fonts))

            if index < len(notes_list) - 1:
                story.append(Spacer(1, 8))
                story.append(HRFlowable(width='100%', thickness=0.7, color=colors.HexColor('#bdbdbd')))
                story.append(Spacer(1, 12))

        doc.build(story)
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


@main_bp.route('/about')
def about():
    try:
        version_path = os.path.join(os.path.dirname(__file__), 'VERSION')
        with open(version_path, 'r') as f:
            version = f.read().strip()
    except Exception:
        version = 'dev'
    return render_template('about.html', version=version)


@main_bp.route('/settings', methods=['GET', 'POST'])
def settings():
    model_fetch_error = None

    if request.method == 'POST':
        ollama_url = request.form.get('ollama_url', '').strip()
        ollama_model = request.form.get('ollama_model', '').strip()
        theme = request.form.get('theme', 'light').strip()

        # Save theme preference
        set_setting_value('theme', theme)

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
    )

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


@main_bp.route('/api/notes/count', methods=['GET'])
def notes_count():
    """API endpoint to return total notes count."""
    try:
        total_notes = Note.query.count()
        return jsonify({'total_notes': total_notes})
    except Exception as e:
        return jsonify({'error': f'Failed to count notes: {str(e)}'}), 500
