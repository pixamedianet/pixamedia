#!/usr/bin/env python3
import re, requests, time, sys

KEY = 'aadf6872a68085f5e90edf98e734d4c2'
HOST = 'pixamedia.net'
SITE = 'https://pixamedia.net'

# sitemap adreslerini oku
s = open('sitemap.xml', encoding='utf-8').read()
urls = re.findall(r'<loc>(https://[^<]+)</loc>', s)
print('sitemap adres:', len(urls))

# anahtar dosyasi canlida 200 mu (yayin gecikmesi icin)
key_url = f'{SITE}/{KEY}.txt'
for _ in range(10):
    try:
        if requests.get(key_url, timeout=15).status_code == 200:
            break
    except Exception:
        pass
    print('  anahtar dosyasi henuz 200 degil, bekleniyor...')
    time.sleep(30)

payload = {
    'host': HOST,
    'key': KEY,
    'keyLocation': key_url,
    'urlList': urls[:10000],
}
try:
    r = requests.post('https://api.indexnow.org/indexnow', json=payload, timeout=60)
    print('IndexNow yanit:', r.status_code, r.text[:200])
except Exception as e:
    print('IndexNow hata:', e)
    sys.exit(1)
