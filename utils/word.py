"""Convert notes to Microsoft Word (.docx) documents with preserved formatting."""

import io
import re

from bs4 import BeautifulSoup, NavigableString, Tag
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor


def _parse_css_style(style_str):
    """Parse CSS style string into a dictionary."""
    attrs = {}
    if not style_str:
        return attrs
    for prop in style_str.split(';'):
        prop = prop.strip()
        if ':' in prop:
            key, value = prop.split(':', 1)
            attrs[key.strip()] = value.strip()
    return attrs


def _css_color_to_hex(color):
    if not color:
        return None
    color = color.strip()
    if re.fullmatch(r'#[0-9a-fA-F]{6}', color):
        return color[1:]
    rgb_match = re.fullmatch(
        r'rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,[^)]*)?\)',
        color,
    )
    if rgb_match and all(int(value) <= 255 for value in rgb_match.groups()):
        return ''.join(f'{int(value):02X}' for value in rgb_match.groups())
    return None


def _add_run_with_formatting(paragraph, text, attrs):
    """Add a run to a paragraph with formatting applied."""
    run = paragraph.add_run(text)
    if attrs.get('bold'):
        run.bold = True
    if attrs.get('italic'):
        run.italic = True
    if attrs.get('underline'):
        run.underline = True
    if attrs.get('strike'):
        run.font.strike = True
    if attrs.get('color'):
        color = _css_color_to_hex(attrs['color'])
        if color:
            run.font.color.rgb = RGBColor.from_string(color)
    if attrs.get('background'):
        bg = _css_color_to_hex(attrs['background'])
        if bg:
            shading = OxmlElement('w:shd')
            shading.set(qn('w:fill'), bg)
            run._r.get_or_add_rPr().append(shading)
    if attrs.get('font'):
        run.font.name = attrs['font']
    if attrs.get('size'):
        size_map = {'1': 10, '2': 13, '3': 16, '4': 18, '5': 24, '6': 32, '7': 48}
        run.font.size = Pt(size_map.get(attrs['size'], 13))
    return run


def _add_hyperlink(doc, paragraph, href, text):
    """Add a hyperlink to a paragraph."""
    r_id = doc.part.relate_to(
        href,
        'http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink',
        is_external=True
    )
    hyperlink = OxmlElement('w:hyperlink')
    hyperlink.set(qn('r:id'), r_id)
    new_run = OxmlElement('w:r')
    rPr = OxmlElement('w:rPr')
    rStyle = OxmlElement('w:rStyle')
    rStyle.set(qn('w:val'), 'Hyperlink')
    rPr.append(rStyle)
    vR = OxmlElement('w:v')
    vR.set(qn('w:val'), href)
    rPr.append(vR)
    new_run.append(rPr)
    t = OxmlElement('w:t')
    t.set(qn('xml:space'), 'preserve')
    t.text = text
    new_run.append(t)
    hyperlink.append(new_run)
    paragraph._p.append(hyperlink)


def _process_inline_elements(element, paragraph, doc, inherited_attrs=None):
    """Process inline HTML elements and preserve nested formatting."""
    inherited_attrs = inherited_attrs or {}
    for child in element.children:
        if isinstance(child, NavigableString):
            text = str(child)
            if text:
                _add_run_with_formatting(paragraph, text, inherited_attrs)
        elif isinstance(child, Tag):
            tag = child.name.lower()
            style = _parse_css_style(child.get('style', ''))
            attrs = dict(inherited_attrs)

            if tag in ('strong', 'b'):
                attrs['bold'] = True
            elif tag in ('em', 'i'):
                attrs['italic'] = True
            elif tag == 'u':
                attrs['underline'] = True
            elif tag in ('s', 'strike', 'del'):
                attrs['strike'] = True
            elif tag == 'a':
                href = child.get('href', '#')
                text = child.get_text()
                _add_hyperlink(doc, paragraph, href, text)
                continue
            elif tag == 'span':
                font_weight = style.get('font-weight', '')
                if font_weight == 'bold' or (
                    font_weight.isdigit() and int(font_weight) >= 600
                ):
                    attrs['bold'] = True
                if style.get('font-style') == 'italic':
                    attrs['italic'] = True
                decoration = style.get('text-decoration', '')
                if 'underline' in decoration:
                    attrs['underline'] = True
                if 'line-through' in decoration:
                    attrs['strike'] = True
                if 'color' in style:
                    attrs['color'] = style['color']
                if 'background-color' in style:
                    attrs['background'] = style['background-color']
                elif 'background' in style:
                    attrs['background'] = style['background']
                if 'font-family' in style:
                    attrs['font'] = style['font-family'].strip("'\"")
                if 'font-size' in style:
                    attrs['size'] = re.sub(r'\D', '', style['font-size'])
            elif tag == 'mark':
                attrs['background'] = '#ffff00'
            elif tag == 'br':
                paragraph.add_run('\n')
                continue
            elif tag == 'code':
                text = child.get_text()
                run = _add_run_with_formatting(paragraph, text, attrs)
                run.font.name = 'Courier New'
                run.font.size = Pt(10)
                continue

            _process_inline_elements(child, paragraph, doc, attrs)


def _add_paragraph_with_formatting(element, doc):
    """Add a paragraph from a <p> element, preserving inline formatting."""
    p = doc.add_paragraph()
    _process_inline_elements(element, p, doc)
    return p


def _add_list(element, doc, ordered=False, level=0):
    """Add an ordered or unordered list."""
    for child in element.children:
        if isinstance(child, Tag) and child.name and child.name.lower() == 'li':
            style = 'List Number' if ordered else 'List Bullet'
            if level:
                style += f' {min(level + 1, 9)}'
            p = doc.add_paragraph(style=style)
            for nested in child.children:
                if isinstance(nested, Tag) and nested.name and nested.name.lower() in ('ul', 'ol'):
                    continue
                if isinstance(nested, NavigableString):
                    if nested.strip():
                        _add_run_with_formatting(p, str(nested), {})
                else:
                    _process_inline_elements(nested, p, doc)
            for nested in child.children:
                if isinstance(nested, Tag) and nested.name and nested.name.lower() in ('ul', 'ol'):
                    _add_list(
                        nested,
                        doc,
                        ordered=(nested.name.lower() == 'ol'),
                        level=level + 1,
                    )


def _set_paragraph_alignment(paragraph, element):
    """Apply alignment from Quill classes or CSS."""
    classes = element.get('class') or []
    style = _parse_css_style(element.get('style', ''))
    alignment = style.get('text-align')
    if 'ql-align-center' in classes or alignment == 'center':
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    elif 'ql-align-right' in classes or alignment == 'right':
        paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    elif 'ql-align-justify' in classes or alignment == 'justify':
        paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY


def _add_table(element, doc):
    rows = element.find_all('tr', recursive=True)
    if not rows:
        return

    width = max((len(row.find_all(['th', 'td'], recursive=False)) for row in rows), default=0)
    if not width:
        return

    table = doc.add_table(rows=0, cols=width)
    table.style = 'Table Grid'
    for row in rows:
        cells = row.find_all(['th', 'td'], recursive=False)
        if not cells:
            continue
        word_row = table.add_row()
        for index, cell in enumerate(cells):
            paragraph = word_row.cells[index].paragraphs[0]
            _process_inline_elements(cell, paragraph, doc)
            if cell.name.lower() == 'th':
                for run in paragraph.runs:
                    run.bold = True


def _add_code_block(element, doc):
    if 'ql-code-block-container' in (element.get('class') or []):
        lines = [
            child.get_text()
            for child in element.children
            if isinstance(child, Tag)
            and 'ql-code-block' in (child.get('class') or [])
        ]
        text = '\n'.join(lines)
    else:
        code = element.find('code')
        text = code.get_text() if code else element.get_text()

    paragraph = doc.add_paragraph(text)
    paragraph.paragraph_format.left_indent = Pt(24)
    paragraph.paragraph_format.right_indent = Pt(24)
    for run in paragraph.runs:
        run.font.name = 'Courier New'
        run.font.size = Pt(10)


def _parse_quill_html(html_content, doc):
    """Parse Quill HTML content and add rich text to the document."""
    if not html_content:
        doc.add_paragraph('(No content)')
        return

    soup = BeautifulSoup(html_content, 'html.parser')

    for element in soup.children:
        if isinstance(element, NavigableString):
            text = str(element).strip()
            if text:
                doc.add_paragraph(text)
        elif isinstance(element, Tag):
            tag = element.name.lower()

            if tag == 'p':
                paragraph = _add_paragraph_with_formatting(element, doc)
                _set_paragraph_alignment(paragraph, element)
            elif tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
                level = int(tag[1])
                heading = doc.add_heading(level=min(level, 6))
                _process_inline_elements(element, heading, doc)
                _set_paragraph_alignment(heading, element)
            elif tag == 'blockquote':
                p = doc.add_paragraph(style='Quote')
                _process_inline_elements(element, p, doc)
                p.paragraph_format.left_indent = Pt(24)
                _set_paragraph_alignment(p, element)
            elif tag == 'pre':
                _add_code_block(element, doc)
            elif tag == 'div' and 'ql-code-block-container' in (element.get('class') or []):
                _add_code_block(element, doc)
            elif tag == 'table':
                _add_table(element, doc)
            elif tag == 'ul':
                _add_list(element, doc, ordered=False)
            elif tag == 'ol':
                _add_list(element, doc, ordered=True)
            elif tag in ('tbody', 'thead', 'tr', 'td'):
                _add_paragraph_with_formatting(element, doc)
            elif tag == 'br':
                doc.add_paragraph()


def notes_to_docx(notes):
    """Convert a list of Note objects to a Word document buffer.

    Args:
        notes: Iterable of Note model instances.

    Returns:
        An io.BytesIO buffer containing the .docx file.
    """
    doc = Document()

    for note in notes:
        # Use note title as the main document heading
        doc.add_heading(note.title if note.title else 'Untitled', level=0)
        doc.add_paragraph()

        # Note content with preserved formatting
        _parse_quill_html(note.content, doc)

        # Separator between notes
        doc.add_paragraph()
        doc.add_paragraph('_' * 40)
        doc.add_paragraph()

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer
