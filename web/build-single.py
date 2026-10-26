#!/usr/bin/env python3
"""index.html + css + js ni bitta tilyoli.html fayliga birlashtiradi: python3 build-single.py"""
import re
h = open('index.html', encoding='utf-8').read()
h = re.sub(r'<link rel="stylesheet" href="([^"/]+\.css)">', lambda m: '<style>\n' + open(m.group(1), encoding='utf-8').read() + '\n</style>', h)
h = re.sub(r'<script src="([^"/]+\.js)"></script>', lambda m: '<script>\n' + open(m.group(1), encoding='utf-8').read().replace('</script', '<\\/script') + '\n</script>', h)
open('tilyoli.html', 'w', encoding='utf-8').write(h)
print('tilyoli.html', len(h) // 1024, 'KB')
