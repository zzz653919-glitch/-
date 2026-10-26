#!/usr/bin/env python3
"""Hamma narsani (sayt + admin panel) bitta tilyoli.html fayliga birlashtiradi:  python3 build-single.py
Fayl ochilganda — o'quvchi ilovasi; `tilyoli.html?admin` — lokal admin panel (server kerak emas)."""
import re

def read(p): return open(p, encoding='utf-8').read()
def js(p): return read(p).replace('</script', '<\\/script')

def inline(html, css_re, js_re):
    html = re.sub(css_re, lambda m: '<style>\n' + read(m.group(1)) + '\n</style>', html)
    # admin rejimida (document.write bilan almashtirilgandan keyin) o'quvchi skriptlari ishlamasligi uchun bayroq
    return re.sub(js_re, lambda m: '<script>\nif(!window.__adm){\n' + js(m.group(1)) + '\n}\n</script>', html)

# --- o'quvchi ilovasi
learner = inline(read('index.html'), r'<link rel="stylesheet" href="([^"/]+\.css)">', r'<script src="([^"/]+\.js)"></script>')

# --- admin panel (lokal rejim: data/content/localapi + admin.js)
admin = read('admin/admin.html')
admin = admin.replace('<script src="/admin/admin.js"></script>', '<script src="/data.js"></script>\n<script src="/content.js"></script>\n<script src="/localapi.js"></script>\n<script src="/admin/admin.js"></script>')
admin = re.sub(r'<link rel="stylesheet" href="/admin/([^"]+)">', lambda m: '<style>\n' + read('admin/' + m.group(1)) + '\n</style>', admin)
admin = re.sub(r'<script src="/admin/([^"]+)"></script>', lambda m: '<script>\n' + js('admin/' + m.group(1)) + '\n</script>', admin)
admin = re.sub(r'<script src="/([^"/]+\.js)"></script>', lambda m: '<script>\n' + js(m.group(1)) + '\n</script>', admin)
admin = admin.replace('</script', '<\\/script')   # tashqi text/plain konteyner ichida yopilib ketmasligi uchun

boot = ("<script id=\"admin-bundle\" type=\"text/plain\">" + admin + "</script>\n"
        "<script>window.TY_SINGLE=true;if(/[?&]admin(&|=|$)/.test(location.search)){window.__adm=true;var b=document.getElementById('admin-bundle').textContent.replace(/<\\\\\\/script/g,'</script');document.open();document.write(b);document.close();}</script>\n")
out = learner.replace('<body>\n', '<body>\n' + boot, 1)
assert boot in out
open('tilyoli.html', 'w', encoding='utf-8').write(out)
print('tilyoli.html', len(out) // 1024, 'KB')
