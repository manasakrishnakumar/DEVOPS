"""Combine the four handoff markdown files into PROJECT_HANDOFF_COMPLETE.pdf (monospace, wrapped)."""
import os
import re
import sys
import textwrap

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, Preformatted, SimpleDocTemplate, Spacer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ['PROJECT_HANDOFF.md', 'IMPLEMENTATION_PHASES.md', 'REFERENCES_AND_LITERATURE_REVIEW.md',
         'TESTING_AND_KNOWN_ISSUES.md']
OUT_NAME = 'PROJECT_HANDOFF_COMPLETE.pdf'
if len(sys.argv) > 2:          # usage: build_handoff_pdf.py OUTPUT.pdf FILE1.md [FILE2.md ...]
    OUT_NAME, FILES = sys.argv[1], sys.argv[2:]
H1 = ParagraphStyle('h1', fontName='Helvetica-Bold', fontSize=15, spaceAfter=6, textColor=colors.HexColor('#1f3864'))
H2 = ParagraphStyle('h2', fontName='Helvetica-Bold', fontSize=11.5, spaceBefore=8, spaceAfter=3,
                    textColor=colors.HexColor('#1f3864'))
H3 = ParagraphStyle('h3', fontName='Helvetica-Bold', fontSize=9.5, spaceBefore=5, spaceAfter=2)
MONO = ParagraphStyle('m', fontName='Courier', fontSize=6.2, leading=7.4)
WIDTH = 150   # characters per line at 6.2 pt on landscape A4 with 1 cm margins


def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def clean(s):
    s = re.sub(r'\*\*(.*?)\*\*', r'\1', s)
    s = re.sub(r'`([^`]*)`', r'\1', s)
    s = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1 (\2)', s)
    return s.encode('latin-1', 'replace').decode('latin-1')


story = []
for fn in FILES:
    path = os.path.join(ROOT, fn)
    story.append(Paragraph(esc(fn), H1))
    buf, in_code = [], False
    for raw in open(path, encoding='utf-8').read().splitlines():
        if raw.strip().startswith('```'):
            in_code = not in_code
            continue
        if in_code:
            buf.append(raw)
            continue
        m = re.match(r'^(#{1,4})\s+(.*)', raw)
        if m:
            if buf:
                story.append(Preformatted('\n'.join(buf), MONO))
                buf = []
            lvl = len(m.group(1))
            story.append(Paragraph(esc(clean(m.group(2))), H1 if lvl == 1 else H2 if lvl == 2 else H3))
            continue
        line = clean(raw)
        if line.startswith('|') and set(line.replace('|', '').strip()) <= set('-: '):
            continue
        for part in (textwrap.wrap(line, WIDTH, subsequent_indent='  ') or ['']):
            buf.append(part)
    if buf:
        story.append(Preformatted('\n'.join(buf), MONO))
    story.append(PageBreak())

out = os.path.join(ROOT, OUT_NAME)
SimpleDocTemplate(out, pagesize=landscape(A4), leftMargin=1 * cm, rightMargin=1 * cm, topMargin=1 * cm,
                  bottomMargin=1 * cm, title='Project Handoff - Complete').build(story)
print('wrote', out, os.path.getsize(out))
