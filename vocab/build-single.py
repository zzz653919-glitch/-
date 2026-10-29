#!/usr/bin/env python3
"""Hamma narsani bitta lugat.html fayliga birlashtiradi:  python3 build-single.py"""
import re
def read(p): return open(p, encoding='utf-8').read()
h = read('index.html')
h = re.sub(r'<link rel="stylesheet" href="([^"]+)">', lambda m: '<style>\n' + read(m.group(1)) + '\n</style>', h)
h = re.sub(r'<script src="([^"]+)"></script>', lambda m: '<script>\n' + read(m.group(1)).replace('</script', '<\\/script') + '\n</script>', h)
open('lugat.html', 'w', encoding='utf-8').write(h)
print('lugat.html', len(h) // 1024, 'KB')
