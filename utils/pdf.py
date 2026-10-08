import io
import importlib
import os
import re
from html import unescape
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    XPreformatted,
)

from utils.helpers import strip_html

PDF_ICON_RE = re.compile(r'[\U0001F1E6-\U0001F1FF\U0001F300-\U0001FAFF\u2600-\u27BF\ufe0f]')


def strip_icons_for_pdf(text):
    """Normalize punctuation and remove emoji/icon glyphs for cleaner PDF output."""
    if not text:
        return ''

    normalized = (
        text
        .replace('\u2011', '-')
        .replace('\u2010', '-')
        .replace('\u2012', '-')
        .replace('\u2013', '-')
        .replace('\u2014', '-')
        .replace('\u2212', '-')
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
