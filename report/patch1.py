import io
p = r'C:/Users/manas/OneDrive/Desktop/bangalore_climate_app_final/devops_project/report/build_report.py'
L = io.open(p, encoding='utf-8').read().split('\n')
L[161] = "        text = re.sub(r'CHAPTER\\t(\\d+)\\t', r'CHAPTER \\1:  ', text)"
L[340] = "            heading('h2', it[1], page_break=(it[1] != 'CHAPTER\\t1\\tINTRODUCTION'))"
L[429] = "        m = re.match(r'CHAPTER (\\d+):  (.*)', text)"
io.open(p, 'w', encoding='utf-8').write('\n'.join(L))
print(L[161], L[340], L[429], sep='\n')
