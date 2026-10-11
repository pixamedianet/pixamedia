import io, re, os, datetime
SITE = r'c:\Users\User\Desktop\Reels Otomatik\pixamedia-site'
def slugify(s): return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')
t = io.open(os.path.join(SITE, 'index.html'), encoding='utf-8').read()

def repl(m):
    name = m.group(1); cls = m.group(2)
    if name == 'All': href = '/'; url = '/'
    else: href = '/category/' + slugify(name); url = href
    return f'<a href="{href}" onclick="event.preventDefault(); filterCat(\'{name}\',this); history.pushState(null,\'\',\'{url}\');" class="{cls}"'

t = re.sub(r"<div onclick=\"filterCat\('([^']+)',this\)\" class=\"([^\"]*)\"", repl, t)
t = re.sub(r'(<p class="text-\[10px\] font-medium mt-1 text-gray-500">[^<]*</p>)</div>', r'\1</a>', t)

jsonld = ('<script type="application/ld+json">{"@context":"https://schema.org","@type":"Organization","name":"PixaMedia","url":"https://pixamedia.net","logo":"https://pixamedia.net/og-image.jpg"}</script>'
          '<script type="application/ld+json">{"@context":"https://schema.org","@type":"WebSite","name":"PixaMedia","url":"https://pixamedia.net"}</script>')
t = t.replace('</head>', jsonld + '</head>', 1)
io.open(os.path.join(SITE, 'index.html'), 'w', encoding='utf-8').write(t)
print('index.html guncellendi; <a> kategori karti:', len(re.findall(r'href="/category/', t)))

cats = [c for c in re.findall(r"filterCat\('([^']+)',this\)", t) if c != 'All']
urls = ['https://pixamedia.net/', 'https://pixamedia.net/about', 'https://pixamedia.net/api', 'https://pixamedia.net/terms', 'https://pixamedia.net/privacy', 'https://pixamedia.net/refund', 'https://pixamedia.net/sandbox']
urls += ['https://pixamedia.net/category/' + slugify(c) for c in cats]
today = datetime.date.today().isoformat()
sm = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
for u in urls:
    sm += f'  <url><loc>{u}</loc><lastmod>{today}</lastmod></url>\n'
sm += '</urlset>'
io.open(os.path.join(SITE, 'sitemap.xml'), 'w', encoding='utf-8').write(sm)
print('sitemap URL sayisi:', len(urls))
