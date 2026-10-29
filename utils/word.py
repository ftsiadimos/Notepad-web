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
        color = attrs['color']
        if color.startswith('#') and len(color) == 7:
            try:
                run.font.color.rgb = RGBColor.from_string(color)
            except Exception:
                pass
        elif color in ('rgb(0,0,0)', '#000000', 'black'):
            run.font.color.rgb = RGBColor(0, 0, 0)
        elif color in ('rgb(255,255,255)', '#ffffff', 'white'):
            run.font.color.rgb = RGBColor(255, 255, 255)
    if attrs.get('background'):
        bg = attrs['background']
        if bg.startswith('#') and len(bg) == 7:
            try:
                run.font.highlight_color = bg
            except Exception:
                pass
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


def _process_inline_elements(element, paragraph, doc):
    """Process inline HTML elements and add them to the paragraph with formatting."""
    for child in element.children:
        if isinstance(child, NavigableString):
            text = str(child)
            if text:
                paragraph.add_run(text)
        elif isinstance(child, Tag):
            tag = child.name.lower()
            style = _parse_css_style(child.get('style', ''))
            attrs = {}

            if tag in ('strong', 'b'):
                attrs['bold'] = True
                _process_inline_elements(child, paragraph, doc)
            elif tag in ('em', 'i'):
                attrs['italic'] = True
                _process_inline_elements(child, paragraph, doc)
            elif tag == 'u':
                attrs['underline'] = True
                _process_inline_elements(child, paragraph, doc)
            elif tag in ('s', 'strike', 'del'):
                attrs['strike'] = True
                _process_inline_elements(child, paragraph, doc)
            elif tag == 'a':
                href = child.get('href', '#')
                text = child.get_text()
                _add_hyperlink(doc, paragraph, href, text)
            elif tag == 'span':
                if 'font-weight: bold' in style or 'font-weight:bold' in style:
                    attrs['bold'] = True
                if 'font-style: italic' in style or 'font-style:italic' in style:
                    attrs['italic'] = True
                if 'text-decoration: underline' in style or 'text-decoration:underline' in style:
                    attrs['underline'] = True
                if 'text-decoration: line-through' in style or 'text-decoration:line-through' in style:
                    attrs['strike'] = True
                if 'color:' in style:
                    color = style.split('color:')[1].split(';')[0].strip()
                    attrs['color'] = color
                if 'background-color:' in style:
                    bg = style.split('background-color:')[1].split(';')[0].strip()
                    attrs['background'] = bg
                elif 'background:' in style and 'color' not in style.split('background:')[1].split(';')[0].strip():
                    bg = style.split('background:')[1].split(';')[0].strip()
                    attrs['background'] = bg
                if 'font-family:' in style:
                    font = style.split('font-family:')[1].split(';')[0].strip().strip("'\"")
                    attrs['font'] = font
                if 'font-size:' in style:
                    size = style.split('font-size:')[1].split(';')[0].strip()
                    attrs['size'] = size
                text = child.get_text()
                if text:
                    _add_run_with_formatting(paragraph, text, attrs)
            elif tag == 'mark':
                # <mark> highlights text with a yellow background
                text = child.get_text()
                if text:
                    run = _add_run_with_formatting(paragraph, text, attrs)
                    run.font.highlight_color = 'FFFF00'  # yellow highlight
            elif tag == 'br':
                paragraph.add_run('\n')
            elif tag == 'code':
                # Inline code - use monospace
                text = child.get_text()
                run = paragraph.add_run(text)
                run.font.name = 'Courier New'
                run.font.size = Pt(10)
            else:
                # Recurse for nested elements
                _process_inline_elements(child, paragraph, doc)


def _add_paragraph_with_formatting(element, doc):
    """Add a paragraph from a <p> element, preserving inline formatting."""
    p = doc.add_paragraph()
    _process_inline_elements(element, p, doc)
    return p


def _add_list(element, doc, ordered=False):
    """Add an ordered or unordered list (always using bullets/dots)."""
    for child in element.children:
        if isinstance(child, Tag) and child.name and child.name.lower() == 'li':
            p = doc.add_paragraph(style='List Bullet')
            _process_inline_elements(child, p, doc)
            # Handle nested lists within li
            for nested in child.children:
                if isinstance(nested, Tag) and nested.name and nested.name.lower() in ('ul', 'ol'):
                    _add_list(nested, doc, ordered=(nested.name.lower() == 'ol'))


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
                _add_paragraph_with_formatting(element, doc)
            elif tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
                level = int(tag[1])
                heading = doc.add_heading(element.get_text(), level=min(level, 6))
                style = _parse_css_style(element.get('style', ''))
                if 'text-align: center' in style:
                    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
                elif 'text-align: right' in style:
                    heading.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                elif 'text-align: justify' in style:
                    heading.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            elif tag == 'blockquote':
                p = doc.add_paragraph(element.get_text(), style='Quote')
                p.paragraph_format.left_indent = Pt(24)
            elif tag == 'pre':
                code = element.find('code')
                code_text = code.get_text() if code else element.get_text()
                p = doc.add_paragraph(code_text)
                p.paragraph_format.left_indent = Pt(24)
                p.paragraph_format.right_indent = Pt(24)
                for run in p.runs:
                    run.font.name = 'Courier New'
                    run.font.size = Pt(10)
            elif tag == 'div' and 'ql-code-block-container' in (element.get('class') or []):
                # Quill code block container
                code_text = element.get_text()
                p = doc.add_paragraph(code_text)
                p.paragraph_format.left_indent = Pt(24)
                p.paragraph_format.right_indent = Pt(24)
                for run in p.runs:
                    run.font.name = 'Courier New'
                    run.font.size = Pt(10)
            elif tag == 'ul':
                _add_list(element, doc, ordered=False)
            elif tag == 'ol':
                _add_list(element, doc, ordered=True)
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
