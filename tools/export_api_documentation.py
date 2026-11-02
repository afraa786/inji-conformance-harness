"""Export the checked-in API reference with installed Markdown and Edge/Playwright.

No dependencies are installed. Existing PDF/HTML exports are preserved.
"""
from pathlib import Path
import hashlib
import json
import re


def main():
    import markdown
    from playwright.sync_api import sync_playwright

    root=Path(__file__).resolve().parents[1]
    out=root/'artifacts/documentation'
    name='Inji Conformance Harness - API Documentation'
    pdf=out/(name+'.pdf')
    html=out/(name+'.html')
    if pdf.exists() or html.exists():
        raise ValueError('Existing documentation export retained; choose a versioned destination before regenerating')
    out.mkdir(parents=True,exist_ok=True)
    source=root/'docs/api-reference.md'
    content=markdown.markdown(source.read_text(encoding='utf-8'),extensions=['tables','fenced_code','toc'],extension_configs={'toc':{'toc_depth':'2-3'}})
    css='''
@page{size:A4;margin:20mm 16mm 18mm}*{box-sizing:border-box}
body{font-family:"Segoe UI",Arial,sans-serif;color:#233247;font-size:10pt;line-height:1.48;margin:0}
h1{font-size:27pt;color:#122c48;line-height:1.2;margin:8mm 0 5mm;border-bottom:4px solid #16a998;padding-bottom:5mm}
h2{font-size:18pt;color:#123c5a;margin:4mm 0;break-before:page;break-after:avoid}
h3{font-size:12pt;color:#145965;margin:6mm 0 2mm;break-after:avoid}
p{margin:2.5mm 0}a{color:#145b93;text-decoration:none;overflow-wrap:anywhere}
code{font-family:Consolas,"Courier New",monospace;font-size:8.4pt;overflow-wrap:anywhere;color:#203951}
pre{background:#f0f5f9;border-left:3px solid #16a998;padding:3mm;white-space:pre-wrap;overflow-wrap:anywhere;font-size:8.4pt;line-height:1.38;break-inside:avoid}
table{border-collapse:collapse;width:100%;font-size:8.8pt;margin:4mm 0;table-layout:fixed}
th{text-align:left;background:#173b57;color:white;padding:2.5mm}td{border-bottom:1px solid #d7e1e9;vertical-align:top;padding:2.5mm;overflow-wrap:anywhere}
thead{display:table-header-group}tr{break-inside:avoid}td code{font-size:8pt}
ul,ol{padding-left:5mm}li{margin:1.6mm 0}.toc{background:#f4f8fa;border:1px solid #d7e1e9;padding:3mm 5mm;font-size:9pt}
.toc ul{margin:1mm 0}.toc li{margin:.5mm 0}.brand{font-size:9pt;letter-spacing:2px;color:#157b75;margin-top:4mm}.notice{border:1px solid #cad9e5;padding:3mm;color:#435871;font-size:9pt;margin-top:5mm}
'''
    page='<!doctype html><html><head><meta charset="utf-8"><title>Inji Conformance Harness — API Documentation</title><style>'+css+'</style></head><body><div class="brand">MOSIP DEC{}DE · TECHNICAL REFERENCE</div>'+content+'<div class="notice">Generated from docs/api-reference.md. Examples contain no real credentials. This document is not an end-to-end conformance certificate.</div></body></html>'
    html.write_text(page,encoding='utf-8')
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path='C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')
        tab=browser.new_page(viewport={'width':794,'height':1123},device_scale_factor=1.5)
        tab.goto(html.as_uri())
        tab.emulate_media(media='print')
        tab.screenshot(path=str(out/'api-documentation-cover.png'))
        tab.pdf(path=str(pdf),format='A4',print_background=True,display_header_footer=True,
                header_template='<div style="font:8px Arial;color:#718092;width:100%;padding:0 17mm">INJI CONFORMANCE HARNESS · API REFERENCE</div>',
                footer_template='<div style="font:8px Arial;color:#718092;width:100%;padding:0 17mm;display:flex;justify-content:space-between"><span>Source-based reference · 02 Nov 2026</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>',
                margin={'top':'20mm','bottom':'18mm','left':'16mm','right':'16mm'})
        checks=tab.evaluate('''() => ({title:document.title,chapters:document.querySelectorAll('h2').length,tables:document.querySelectorAll('table').length,codeBlocks:document.querySelectorAll('pre').length,overflow:[...document.querySelectorAll('pre,table')].filter(x=>x.scrollWidth>x.clientWidth+2).length})''')
        tab.locator('h2').filter(has_text='Verify APIs and DCQL presentation flow').scroll_into_view_if_needed()
        tab.screenshot(path=str(out/'api-documentation-verify-preview.png'))
        browser.close()
    data=pdf.read_bytes()
    pages=len(re.findall(rb'/Type\s*/Page\b',data))
    assert data.startswith(b'%PDF-') and b'%%EOF' in data[-1024:] and pages>1
    assert checks['overflow']==0 and checks['chapters']==11
    info=dict(pdf=pdf.relative_to(root).as_posix(),bytes=len(data),pages=pages,sha256=hashlib.sha256(data).hexdigest(),
              source=source.relative_to(root).as_posix(),sourceSha256=hashlib.sha256(source.read_bytes()).hexdigest(),
              validation='Chromium PDF export, valid PDF header/EOF, page objects counted, source layout checks; no API execution',layout=checks)
    (out/'api-documentation-verification.json').write_text(json.dumps(info,indent=2),encoding='utf-8')
    print(json.dumps(info,indent=2))


if __name__=='__main__': main()
