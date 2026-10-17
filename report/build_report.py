"""Builds the project report DOCX from the college template (AIML- Project Report.docx).
   python -X utf8 report/build_report.py [pages.json]      -> report/Project_Report.docx
Front matter of the template is kept and edited in place; everything from the chapter stub on is regenerated.
"""
import copy
import json
import os
import re
import sys

import docx
import pandas as pd
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor, Inches

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import c1, c2, c4, c5, c6, c7  # noqa: E402

TEMPLATE = r'C:/Users/manas/Downloads/AIML- Project Report.docx'
OUT = os.path.join(HERE, 'Project_Report_v2.docx')
PAGES = json.load(open(sys.argv[1])) if len(sys.argv) > 1 and os.path.exists(sys.argv[1]) else {}
NAME1, NAME2, USN = '[STUDENT NAME 1]', '[STUDENT NAME 2]', '[USN]'
TITLE = c1.TITLE
FONT = 'Times New Roman'

d = docx.Document(TEMPLATE)
body = d.element.body
kids = list(body)
P = d.paragraphs


def set_text(p, text):
    runs = p.runs
    if not runs:
        p.add_run(text)
        return
    runs[0].text = text
    for r in runs[1:]:
        r._r.getparent().remove(r._r)


def clone_after(ref_el, text, bold=None):
    el = copy.deepcopy(ref_el)
    ref_el.addnext(el)
    from docx.text.paragraph import Paragraph
    p = Paragraph(el, d._body)
    set_text(p, text)
    for r in p.runs:
        if bold is not None:
            r.bold = bold
    return p


# ---------- templates for body paragraphs (before deletion) ----------
BODY_P = copy.deepcopy(P[172]._p)       # 'Your text here' justified TNR 12
CH_P = copy.deepcopy(P[171]._p)         # Heading 2 'CHAPTER 1 ...'
H3_P = copy.deepcopy(P[174]._p)         # Heading 3 'Terminology'
for el in (BODY_P, CH_P, H3_P):
    for s in list(el.iter(qn('w:sectPr'))):
        s.getparent().remove(s)

# ---------- front matter edits ----------
set_text(P[11], TITLE)
P[11].alignment = WD_ALIGN_PARAGRAPH.CENTER
for r in P[11].runs:
    r.font.size = Pt(20)
    r.bold = True
set_text(P[16], f'{NAME1}\t{USN}')
set_text(P[17], f'{NAME2}\t{USN}')
t46 = P[46].text.replace('“Title”', f'“{TITLE}”').replace('by Name (USN) and Name (USN)', f'by {NAME1} ({USN}) and {NAME2} ({USN})')
set_text(P[46], t46)
set_text(P[74], f'We, {NAME1} and {NAME2}, students of fifth semester B.E., Department of Information Science and Engineering, RV College of Engineering, Bengaluru, hereby declare that the project titled “{TITLE}” has been carried out by us and submitted in partial fulfilment for the award of degree of Bachelor of Engineering in Information Science and Engineering during the year 2025-2026.')
set_text(P[75], 'Further we declare that the content of the dissertation has not been submitted previously by anybody for the award of any degree or diploma to any other university.')
set_text(P[76], 'We also declare that any Intellectual property rights generated out of this project carried out at RVCE will be the property of RV College of Engineering, Bengaluru and we will be among the authors of the same.')

ACK = ("We express our sincere gratitude to our guide, Dr. Merin Meleet, Associate Professor, Department of Information Science and Engineering, RV College of Engineering, for her constant guidance, encouragement and valuable suggestions throughout this project. "
       "We thank the Head of the Department of Information Science and Engineering and the faculty of the department for providing the laboratory facilities and an environment that made this work possible. "
       "We are grateful to the Principal of RV College of Engineering for the academic support. "
       "We also thank the authors of the open-source tools on which this work stands - Docker, Kubernetes, Minikube, Prometheus, Grafana, OpenTelemetry, Jaeger, Argo Rollouts, Kyverno, cosign, KEDA, Chaos Mesh, Flask, TensorFlow, statsmodels, scikit-learn and kopf - and the authors of the research papers whose work we reviewed. "
       "Finally, we thank our families and friends for their patience and support during long experiment runs.")
ABS = ("Container orchestrators such as Kubernetes restart a service whose process fails, but a machine-learning service can fail silently: it keeps answering HTTP 200 with well-formed but wrong values, so the default liveness and readiness probes never react. "
       "This project studies that blind spot using the Bangalore Climate Analytics System, a forecasting application (SARIMA and a real trained LSTM) that was re-engineered from a Flask monolith into a containerised, Kubernetes-hosted system with a frontend, an inference service and PostgreSQL, observed with Prometheus, Grafana and OpenTelemetry. "
       "A silent-fault benchmark (SilentBench) with eight injected faults shows that with default probes every silent fault produced 100 percent wrong answers and none was detected (10 trials per cell). "
       "We design and evaluate a layered correctness guard consisting of a window-level split-conformal envelope, temporal invariants, a cross-model canary and a golden-output integrity check, combined with four-tier graceful degradation, a correctness service-level objective, a Kubernetes operator that restores full quality, a precursor-based failure predictor, a shadow-traffic delivery gate and deadline- and load-aware degradation. "
       "The full guard served 0 percent wrong answers for all injected faults, including subtle bit flips that evade the other layers, and raised no false alarm in healthy control, in a ten-minute soak or on hold-out windows. "
       "The operator restored full quality in 20 of 20 trials in about 22 to 24 seconds, whereas the service never recovered without it; the memory-leak predictor warned 69.6 seconds before failure; the shadow gate rejected 15 of 15 bad candidate models and promoted 6 of 6 good ones; and deadline-aware degradation reduced failed requests under a delay fault from 96.8 percent to 0 percent. "
       "Negative and inconclusive results (probe tuning, learned recovery policy, log-based detection, single-node scaling) are reported with the limitations of the study. "
       "All code, raw results and documents are packaged for reproduction, and a condensed research paper is included in Appendix B.")


def fill_after(heading_idx, text):
    """Put text in the first empty paragraph after a heading paragraph (index in d.paragraphs)."""
    p = P[heading_idx + 1]
    for r in list(p.runs):
        r._r.getparent().remove(r._r)
    run = p.add_run(text)
    run.font.name = FONT
    run.font.size = Pt(12)
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.line_spacing = 1.5


fill_after(85, ACK)
P[86].paragraph_format.right_indent = Cm(1.7)
P[46].paragraph_format.right_indent = Cm(1.0)
t0 = d.tables[0]
cells = t0.rows[3].cells
for cell, lines, al in ((cells[0], ['List of Tables', 'List of Abbreviations', 'Publication Details'], WD_ALIGN_PARAGRAPH.LEFT), (cells[2], ['vi', 'vii', 'viii'], WD_ALIGN_PARAGRAPH.RIGHT)):
    for extra in list(cell.paragraphs):
        extra._p.getparent().remove(extra._p)
    for ln in lines:
        pp = cell.add_paragraph()
        r = pp.add_run(ln)
        r.font.name, r.font.size, r.bold = FONT, Pt(12), True
        pp.alignment = al
        pp.paragraph_format.space_after = Pt(6)

# ---------- helper builders for generated body ----------
sect_ch = copy.deepcopy(kids[177].find('.//' + qn('w:sectPr')))
pgn = sect_ch.find(qn('w:pgNumType'))
if pgn is not None:
    pgn.set(qn('w:start'), '1')
anchor = kids[173]          # first element of the template chapter stub (Heading 2 CHAPTER 1)
# remove everything from the chapter stub up to (excluding) the final sectPr
for el in kids[173:-1]:
    body.remove(el)
body.remove(body[-1])
body.append(sect_ch)
final_sect = body[-1]
HEADINGS = []   # (kind, text) for TOC building
CAPTIONS = []   # (kind, text)


def new_p(el_template):
    el = copy.deepcopy(el_template)
    final_sect.addprevious(el)
    from docx.text.paragraph import Paragraph
    return Paragraph(el, d._body)


def para(text, align='j', size=12, bold=False, italic=False, font=FONT, spacing=1.5, after=6, keep=False):
    p = new_p(BODY_P)
    set_text(p, text)
    for r in p.runs:
        r.font.name = font
        r.font.size = Pt(size)
        r.bold = bold
        r.italic = italic
    p.alignment = {'j': WD_ALIGN_PARAGRAPH.JUSTIFY, 'c': WD_ALIGN_PARAGRAPH.CENTER, 'l': WD_ALIGN_PARAGRAPH.LEFT}[align]
    p.paragraph_format.line_spacing = spacing
    p.paragraph_format.space_after = Pt(after)
    p.paragraph_format.keep_with_next = keep
    return p


def heading(kind, text, page_break=False):
    if kind == 'h2' and text.startswith('CHAPTER'):
        text = re.sub(r'CHAPTER\t(\d+)\t', r'CHAPTER \1:  ', text)
    p = new_p(CH_P if kind == 'h2' else H3_P)
    set_text(p, text)
    if kind == 'h5':
        p.style = d.styles['Heading 5']
    pPr = p._p.get_or_add_pPr()
    for n in list(pPr.findall(qn('w:numPr'))):
        pPr.remove(n)
    npr = OxmlElement('w:numPr')
    nid = OxmlElement('w:numId')
    nid.set(qn('w:val'), '0')
    npr.append(nid)
    pPr.append(npr)
    p.paragraph_format.left_indent = Cm(0)
    p.paragraph_format.first_line_indent = Cm(0)
    if kind in ('h3', 'h5'):
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.keep_with_next = True
    if kind == 'h2':
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if page_break:
        p.paragraph_format.page_break_before = True
    HEADINGS.append((kind, text))
    return p


def bullets(items):
    for it in items:
        p = para('•\t' + it, spacing=1.3, after=3)
        p.paragraph_format.left_indent = Cm(0.9)
        p.paragraph_format.first_line_indent = Cm(-0.6)


def shade(cell, color):
    tcPr = cell._tc.get_or_add_tcPr()
    sh = OxmlElement('w:shd')
    sh.set(qn('w:val'), 'clear')
    sh.set(qn('w:color'), 'auto')
    sh.set(qn('w:fill'), color)
    tcPr.append(sh)


def borders(tbl):
    tblPr = tbl._tbl.tblPr
    b = OxmlElement('w:tblBorders')
    for k in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        e = OxmlElement(f'w:{k}')
        e.set(qn('w:val'), 'single')
        e.set(qn('w:sz'), '4')
        e.set(qn('w:space'), '0')
        e.set(qn('w:color'), '444444')
        b.append(e)
    tblPr.append(b)


def table(header, rows, size=9.5, widths=None):
    tbl = d.add_table(rows=1 + len(rows), cols=len(header))
    final_sect.addprevious(tbl._tbl)
    borders(tbl)
    tbl.autofit = True
    for j, h in enumerate(header):
        c = tbl.rows[0].cells[j]
        c.text = ''
        r = c.paragraphs[0].add_run(h)
        r.bold = True
        r.font.size = Pt(size)
        r.font.name = FONT
        shade(c, 'D9E2F3')
    for i, row in enumerate(rows):
        for j, v in enumerate(row):
            c = tbl.rows[i + 1].cells[j]
            c.text = ''
            r = c.paragraphs[0].add_run(str(v))
            r.font.size = Pt(size)
            r.font.name = FONT
    for row in tbl.rows:
        for c in row.cells:
            for p in c.paragraphs:
                p.paragraph_format.space_after = Pt(1)
                p.paragraph_format.line_spacing = 1.0
    if not widths:
        wts = []
        for j in range(len(header)):
            L = [len(str(r[j])) for r in rows] + [len(header[j])]
            wts.append(max(6, min(70, sum(L) / len(L))))
        tot = sum(wts)
        widths = [14.8 * w / tot for w in wts]
    for row in tbl.rows:
        for j, w in enumerate(widths):
            row.cells[j].width = Cm(w)
    # repeat header row
    trPr = tbl.rows[0]._tr.get_or_add_trPr()
    th = OxmlElement('w:tblHeader')
    th.set(qn('w:val'), 'true')
    trPr.append(th)
    return tbl


def caption(text, kind):
    p = para(text, align='c', size=11, bold=True, spacing=1.0, after=10)
    CAPTIONS.append((kind, text))
    return p


def figure(fname, cap, width_in):
    p = new_p(BODY_P)
    set_text(p, '')
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(os.path.join(HERE, 'assets', fname), width=Inches(width_in))
    caption(cap, 'fig')


def code(file, marker, n, cap):
    src = open(os.path.join(ROOT, file), encoding='utf-8').read().split('\n')
    i = next(k for k, l in enumerate(src) if marker in l)
    lines = [l.rstrip() for l in src[i:i + n]]
    tbl = d.add_table(rows=1, cols=1)
    final_sect.addprevious(tbl._tbl)
    borders(tbl)
    c = tbl.rows[0].cells[0]
    shade(c, 'F2F2F2')
    c.text = ''
    first = True
    for l in lines:
        p = c.paragraphs[0] if first else c.add_paragraph()
        first = False
        r = p.add_run(l if l else ' ')
        r.font.name = 'Courier New'
        r.font.size = Pt(8)
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.line_spacing = 1.0
    caption(cap, 'code')


# ---------- computed tables ----------
def lit_table():
    md = open(os.path.join(ROOT, 'REFERENCES_AND_LITERATURE_REVIEW.md'), encoding='utf-8').read().split('\n')
    rows = []
    for l in md:
        if re.match(r'\| A\d+ ', l):
            c = [x.strip() for x in l.strip().strip('|').split('|')]
            rows.append([c[0], f'{c[1]} ({c[2]}, {c[3]})', c[4], c[5], c[6], c[7]])
    table(['#', 'Paper (authors, year)', 'Problem / method', 'Key result', 'Limitation / gap', 'Relevance to this project'], rows, size=7.5,
          widths=[0.9, 3.6, 3.0, 2.4, 2.4, 2.8])


def data_table():
    df = pd.read_csv(os.path.join(ROOT, 'frontend', 'data.csv'))
    rows = []
    for col, unit in (('Rain', 'mm'), ('Temp Max', 'deg C'), ('Temp Min', 'deg C'), ('Humidity', '%')):
        s = pd.to_numeric(df[col], errors='coerce')
        rows.append([f'{col} ({unit})', f'{int(s.count()):,}', f'{s.mean():.2f}', f'{s.std():.2f}', f'{s.min():.2f}', f'{s.max():.2f}'])
    table(['Variable', 'Count', 'Mean', 'Std', 'Min', 'Max'], rows)


def fault_table():
    rows_in = [json.loads(l) for l in open(os.path.join(ROOT, 'results', 'fault_trials.jsonl')) if l.strip()]
    g = {}
    for r in rows_in:
        g.setdefault((r['config'], r['fault']), []).append(r)
    rows = []
    for (cfg, fault), v in sorted(g.items()):
        rec = [x['recovery_s'] for x in v if x.get('recovery_s') is not None]
        fp = sum(x.get('failed_pct') or 0 for x in v) / len(v)
        rows.append([cfg, fault, len(v), f'{len(rec)}/{len(v)}', f'{sum(rec) / len(rec):.1f}' if rec else '-', f'{fp:.1f}'])
    table(['Config', 'Fault', 'Trials', 'Recovered', 'Mean recovery (s)', 'Mean failed requests (%)'], rows)


def silent_table():
    md = open(os.path.join(ROOT, 'results', 'phase14_tables.md'), encoding='utf-8').read().split('\n')
    rows, on = [], False
    for l in md:
        if l.startswith('## Silent'):
            on = True
        elif l.startswith('## Operator'):
            break
        elif on and l.startswith('|') and not l.startswith('|---') and not l.startswith('| fault'):
            rows.append([x.strip() for x in l.strip().strip('|').split('|')])
    table(['Fault', 'C4 guard off', 'D4 envelope', 'E4 + invariants', 'G4 + golden', 'Fisher C4 vs G4'], rows, size=8)


def val_table():
    md = open(os.path.join(ROOT, 'results', 'validation_report.md'), encoding='utf-8').read().split('\n')
    rows = []
    for l in md:
        if re.match(r'\| V\d+ ', l):
            c = [x.strip() for x in l.strip().strip('|').split('|')]
            rows.append([c[0], c[1].replace('*', ''), c[2][:150]])
    rows.sort(key=lambda r: r[0])
    table(['Check', 'Result', 'Evidence'], rows, size=8, widths=[5.6, 1.4, 8.6])


EXTRA = {'littable': lit_table, 'datatable': data_table, 'faulttable': fault_table, 'silenttable': silent_table, 'valtable': val_table}


def render(items):
    for it in items:
        k = it[0]
        if k == 'h2':
            heading('h2', it[1], page_break=(it[1] != 'CHAPTER\t1\tINTRODUCTION'))
        elif k in ('h3', 'h5'):
            heading(k, it[1])
        elif k == 'p':
            para(it[1])
        elif k == 'bullets':
            bullets(it[1])
        elif k == 'table':
            table(it[1], it[2])
        elif k == 'cap':
            caption(it[1], 'table')
        elif k == 'fig':
            figure(it[1], it[2], it[3])
        elif k == 'code':
            code(it[1], it[2], it[3], it[4])
        elif k in EXTRA:
            EXTRA[k]()


for mod in (c1, c2, c4, c5, c6, c7):
    render(mod.ITEMS)

# references
heading('h2', 'REFERENCES (IEEE FORMAT)', page_break=True)
for i, r in enumerate(c7.REFS, 1):
    p = para(f'[{i}]\t{r}', spacing=1.2, after=4)
    p.paragraph_format.left_indent = Cm(1.0)
    p.paragraph_format.first_line_indent = Cm(-1.0)
para("Note: the first twenty-three entries are the papers supplied as the reading list; authors, years and venues are those visible on the first page or in the title and must be completed from IEEE Xplore before submission to a conference or journal.", size=10, italic=True)

# appendices
heading('h2', 'APPENDIX A  DATASET SAMPLE', page_break=True)
para("First rows of the daily data file (data.csv) and a sample of rows from the year 2018, as read by the application.")
df = pd.read_csv(os.path.join(ROOT, 'frontend', 'data.csv'))
table(list(df.columns), [[str(x) for x in r] for r in df.head(15).values.tolist()], size=9)
caption('Table A.1  First 15 rows of data.csv', 'table')
mid = df[df['Date'].str.startswith('2018-07')].head(10)
table(list(df.columns), [[str(x) for x in r] for r in mid.values.tolist()], size=9)
caption('Table A.2  Ten rows from July 2018', 'table')
para(f"The file contains {len(df):,} daily rows from {df['Date'].iloc[0]} to {df['Date'].iloc[-1]}.")
heading('h2', 'APPENDIX B  RESEARCH PAPER (IEEE FORMAT)', page_break=True)
para("The following is a condensed draft of the research paper that summarises this project. It is written in a single column here; the IEEE two-column template should be applied when it is submitted.", size=11, italic=True)
for it in c7.PAPER:
    if it[0] == 'h5':
        heading('h5', it[1])
    else:
        para(it[1], size=11, spacing=1.15)

# ---------- list of figures / tables / TOC / abbreviations in the front matter ----------
def pg(text):
    return str(PAGES.get(text, ''))


def rebuild_lines(first_k, last_k, model_k, entries):
    """Replace body children first_k..last_k (inclusive, original indexes) with cloned lines of model child."""
    model = kids[model_k]
    keep_sect = None
    for k in range(first_k, last_k + 1):
        s = kids[k].find('.//' + qn('w:sectPr')) if kids[k].tag.endswith('}p') else None
        if s is not None:
            keep_sect = copy.deepcopy(s)
        if k != model_k:
            body.remove(kids[k]) if kids[k].getparent() is body else None
    cur = model
    ps = []
    for txt in entries:
        el = copy.deepcopy(model)
        for s in list(el.iter(qn('w:sectPr'))):
            s.getparent().remove(s)
        for n in list(el.iter(qn('w:numPr'))):
            n.getparent().remove(n)
        cur.addnext(el)
        cur = el
        from docx.text.paragraph import Paragraph
        p = Paragraph(el, d._body)
        set_text(p, txt)
        ps.append(p)
    body.remove(model)
    if keep_sect is not None and ps:
        ps[-1]._p.get_or_add_pPr().append(keep_sect)


def smart(s):
    return ' '.join(w.lower() if w.lower() in ('of', 'and', 'the', 'to') else (w if w.isupper() and len(w) <= 5 and w not in ('CHAPTER',) and False else w.capitalize()) for w in s.split())


chap_entries = []
for kind, text in HEADINGS:
    if kind == 'h2':
        m = re.match(r'CHAPTER (\d+):  (.*)', text)
        label = f'Chapter {m.group(1)}  ' + smart(m.group(2)) if m else text.title()
        chap_entries.append(f'{label}\t{pg(text)}')
    elif kind == 'h3':
        chap_entries.append(f'      {text}\t{pg(text)}')
rebuild_lines(94, 135, 94, chap_entries)

fig_entries = [f"{t.split('  ')[0]}   {t.split('  ', 1)[1]}\t{pg(t)}" for k, t in CAPTIONS if k == 'fig']
rebuild_lines(142, 150, 142, fig_entries)

# list of tables: rebuild rows of the template table
tt = d.tables[1]
tbl_caps = [t for k, t in CAPTIONS if k == 'table']
model_row = copy.deepcopy(tt.rows[0]._tr)
for r in list(tt.rows):
    tt._tbl.remove(r._tr)
for t in tbl_caps:
    tr = copy.deepcopy(model_row)
    tt._tbl.append(tr)
    from docx.table import _Row
    row = _Row(tr, tt)
    a, b = t.split('  ', 1)
    for cell, val in zip(row.cells, (f'{a}   {b}', '', pg(t))):
        ps = cell.paragraphs
        if ps and ps[0].runs:
            set_text(ps[0], val)
        else:
            cell.paragraphs[0].add_run(val)

ABBR = [('AIML', 'Artificial Intelligence and Machine Learning'), ('API', 'Application Programming Interface'), ('ARIMA', 'Autoregressive Integrated Moving Average'),
        ('CI/CD', 'Continuous Integration / Continuous Deployment'), ('CPU', 'Central Processing Unit'), ('CRD', 'Custom Resource Definition'),
        ('DevOps', 'Development and Operations'), ('DoE', 'Design of Experiments'), ('HPA', 'Horizontal Pod Autoscaler'), ('HTTP', 'Hypertext Transfer Protocol'),
        ('IEEE', 'Institute of Electrical and Electronics Engineers'), ('JSON', 'JavaScript Object Notation'), ('K8s', 'Kubernetes'), ('KEDA', 'Kubernetes Event-Driven Autoscaling'),
        ('LFS', 'Large File Storage (Git)'), ('LSTM', 'Long Short-Term Memory'), ('ML', 'Machine Learning'), ('MLOps', 'Machine-Learning Operations'),
        ('MTTC', 'Mean Time To Correctness'), ('MTTR', 'Mean Time To Recovery'), ('PSI', 'Population Stability Index'), ('RL', 'Reinforcement Learning'),
        ('RSM', 'Response Surface Methodology'), ('SARIMA', 'Seasonal Autoregressive Integrated Moving Average'), ('SLI', 'Service-Level Indicator'),
        ('SLO', 'Service-Level Objective'), ('UCB', 'Upper Confidence Bound'), ('YAML', "YAML Ain't Markup Language")]
rebuild_lines(163, 171, 163, [f'{a}\t-\t{b}' for a, b in ABBR])

set_text(P[135], '')
for rel in d.part.rels.values():
    if 'header' in rel.reltype and rel.target_part.partname.endswith('header2.xml'):
        hp = rel.target_part
        for t in hp.element.iter(qn('w:t')):
            if (t.text or '').strip() == 'Title':
                t.text = 'Self-Healing ML Services on K8s'
d.save(OUT)
json.dump({'headings': HEADINGS, 'captions': CAPTIONS}, open(os.path.join(HERE, 'index.json'), 'w'), indent=0)
print('saved', OUT, len(HEADINGS), 'headings', len(CAPTIONS), 'captions')
