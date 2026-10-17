import json, os, sys
import win32com.client as w
HERE = os.path.dirname(os.path.abspath(__file__))
idx = json.load(open(os.path.join(HERE, 'index.json')))
want = {t for _, t in idx['headings']} | {t for _, t in idx['captions']}
app = w.Dispatch('Word.Application'); app.Visible = False
doc = app.Documents.Open(os.path.join(HERE, 'Project_Report_v2.docx'), ReadOnly=True)
doc.Repaginate()
pages = {}
for p in doc.Paragraphs:
    t = p.Range.Text.strip('\r\x07\n').strip()
    if t in want and t not in pages:
        pages[t] = p.Range.Information(1)
print('total pages', doc.ComputeStatistics(2), 'matched', len(pages), 'of', len(want))
doc.ExportAsFixedFormat(os.path.join(HERE, 'Project_Report_v2.pdf'), 17)
doc.Close(False); app.Quit()
json.dump(pages, open(os.path.join(HERE, 'pages.json'), 'w'), indent=0)
