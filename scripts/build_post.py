import io, re, os, json, datetime, subprocess, hashlib
SITE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
if '"@type":"WebSite"' not in t:
    t = t.replace('</head>', jsonld + '</head>', 1)
io.open(os.path.join(SITE, 'index.html'), 'w', encoding='utf-8', newline='\n').write(t)
print('index.html guncellendi; <a> kategori karti:', len(re.findall(r'href="/category/', t)))

cats = [c for c in re.findall(r"filterCat\('([^']+)',this\)", t) if c != 'All']
# sitemap_dates.json: her sayfa icin gercek olusturulma/degisiklik tarihi (slug -> {date, sha})
SD_FILE = os.path.join(SITE, 'scripts', 'sitemap_dates.json')
try:
    sdates = json.load(open(SD_FILE, encoding='utf-8'))
except Exception:
    sdates = {}
today = datetime.date.today().isoformat()

def _sha(rel):
    p = os.path.join(SITE, rel)
    if not os.path.exists(p):
        return None
    try:
        txt = io.open(p, encoding='utf-8', errors='replace').read().replace('\r\n', '\n')
        return hashlib.sha1(txt.encode('utf-8')).hexdigest()
    except Exception:
        return None

def _git_last_dates(paths):
    if isinstance(paths, str):
        paths = [paths]
    res = {}
    try:
        out = subprocess.run(['git', '-C', SITE, 'log', '-n', '3000', '--format=__D__%cs', '--name-only', '--'] + paths,
                             capture_output=True, text=True, timeout=180).stdout
        cur = None
        for ln in out.splitlines():
            if ln.startswith('__D__'):
                cur = ln[5:].strip()
            elif ln.strip() and cur:
                f = ln.strip()
                if f not in res:
                    res[f] = cur
    except Exception:
        pass
    return res

gitmap = {}
gitmap.update(_git_last_dates('a/'))
gitmap.update(_git_last_dates('category/'))
gitmap.update(_git_last_dates(['index.html', 'about.html', 'api.html', 'terms.html', 'privacy.html', 'refund.html']))

def _git_last_date(rel):
    d = gitmap.get(rel)
    return d

def date_for(rel):
    sha = _sha(rel)
    rec = sdates.get(rel)
    if rec:
        if sha and rec.get('sha') == sha:
            return rec.get('date') or today
        d = _git_last_date(rel) or today
        sdates[rel] = {'date': d, 'sha': sha}
        return d
    d = gitmap.get(rel) or today
    sdates[rel] = {'date': d, 'sha': sha}
    return d

pairs = [('https://pixamedia.net/', 'index.html')]
for nm in ['about', 'api', 'terms', 'privacy', 'refund']:
    pairs.append((f'https://pixamedia.net/{nm}', f'{nm}.html'))
for c in cats:
    s = slugify(c)
    pairs.append((f'https://pixamedia.net/category/{s}/', f'category/{s}/index.html'))
selp = os.path.join(SITE, 'scripts', 'asset_pages_selected.json')
if os.path.exists(selp):
    sel = json.load(open(selp, encoding='utf-8'))
    for e in sel.values():
        if not e.get('hidden'):
            pairs.append((f'https://pixamedia.net/a/{e["slug"]}/', f'a/{e["slug"]}/index.html'))
sm = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
for u, rel in pairs:
    sm += f'  <url><loc>{u}</loc><lastmod>{date_for(rel)}</lastmod></url>\n'
sm += '</urlset>'
io.open(os.path.join(SITE, 'sitemap.xml'), 'w', encoding='utf-8', newline='\n').write(sm)
json.dump(sdates, io.open(SD_FILE, 'w', encoding='utf-8', newline='\n'), ensure_ascii=False, indent=0, sort_keys=True)
print('sitemap URL sayisi:', len(pairs))
