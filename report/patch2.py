import io
p = r'C:/Users/manas/OneDrive/Desktop/bangalore_climate_app_final/devops_project/report/build_report.py'
a = io.open(p, encoding='utf-8').read()


def rep(o, n):
    global a
    assert o in a, o[:60]
    a = a.replace(o, n, 1)


# header text through the part's XML element
rep("""        blob = hp.blob.decode('utf8')
        blob = blob.replace('>Title<', '>Correctness-Aware Self-Healing for ML Services on Kubernetes<')
        hp._blob = blob.encode('utf8')""",
    """        for t in hp.element.iter(qn('w:t')):
            if (t.text or '').strip() == 'Title':
                t.text = 'Correctness-Aware Self-Healing for ML Services on Kubernetes'""")

# no automatic numbering / indents on headings; centred chapter headings
rep("""    p = new_p(CH_P if kind == 'h2' else H3_P)
    set_text(p, text)
    if kind == 'h5':
        p.style = d.styles['Heading 5']""",
    """    p = new_p(CH_P if kind == 'h2' else H3_P)
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
    if kind == 'h2':
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER""")

# column widths proportional to content
rep("""    if widths:
        for row in tbl.rows:
            for j, w in enumerate(widths):
                row.cells[j].width = Cm(w)""",
    """    if not widths:
        wts = []
        for j in range(len(header)):
            L = [len(str(r[j])) for r in rows] + [len(header[j])]
            wts.append(max(6, min(70, sum(L) / len(L))))
        tot = sum(wts)
        widths = [15.4 * w / tot for w in wts]
    for row in tbl.rows:
        for j, w in enumerate(widths):
            row.cells[j].width = Cm(w)""")
io.open(p, 'w', encoding='utf-8').write(a)
print('patched')
