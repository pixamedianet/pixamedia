#!/usr/bin/env python3
import io, re, os, json, urllib.parse, requests
from collections import Counter, defaultdict
from html import escape as esc
SITE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = 'https://qxawiooxixrkhjauibxw.supabase.co'
KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InF4YXdpb294aXhya2hqYXVpYnh3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzk4MjczMTYsImV4cCI6MjA5NTQwMzMxNn0.UfDPc-_tr45TbN9eZace4g9Sy5_1vqMGbbSit_VutKM'
H = {'apikey': KEY, 'Authorization': 'Bearer ' + KEY}

def slugify(s): return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')

def count_type(cat, typ):
    catf = 'ilike.*SFX' if cat == 'SFX' else f'eq.{urllib.parse.quote(cat)}'
    r = requests.head(f"{BASE}/rest/v1/contents?select=id&hidden=eq.false&category={catf}&type=eq.{typ}", headers={**H, 'Prefer': 'count=exact'}, timeout=40)
    cr = r.headers.get('content-range', '')
    return int(cr.split('/')[-1]) if '/' in cr else 0

def round50(n): return str(n) if n < 50 else f"{(n // 50) * 50}+"

def kind(v, im, au):
    if au > 0 and v == 0 and im == 0: return 'audio'
    if im > 0 and v == 0: return 'image'
    return 'video_image'

def cat_title(cat, k):
    if k == 'sfx': return 'Free AI Sound Effects | PixaMedia'
    if k == 'audio': return 'Free AI Music Tracks | PixaMedia'
    if k == 'image':
        if cat == 'Coloring Pages': return 'Free Printable Coloring Pages | PixaMedia'
        return f'Free {cat} Printable Pages | PixaMedia'
    return f'Free 4K {cat} Stock Footage & AI Images | PixaMedia'

def cat_desc(cat, k, n):
    if k == 'sfx': d = f"Browse {n} AI-generated sound effects: nature, battle, space, urban and cinematic. Watermark-free. 2 free downloads per day."
    elif k == 'audio': d = f"Browse {n} AI-generated music tracks. Watermark-free. 2 free downloads per day."
    elif k == 'image': d = f"Browse {n} AI-generated printable coloring pages. Watermark-free. 2 free downloads per day."
    else: d = f"Browse {n} AI-generated {cat.lower()} videos and images in 4K/8K. Watermark-free. 2 free downloads per day."
    return d[:157] + '...' if len(d) > 160 else d

def cat_h1(cat, k): return cat_title(cat, k).replace(' | PixaMedia', '')

tpl = io.open(os.path.join(SITE, 'index.html'), encoding='utf-8').read()
cats = [c for c in re.findall(r"filterCat\('([^']+)',this\)", tpl) if c != 'All']
catmap = json.dumps({slugify(c): c for c in cats})
try:
    cat_texts = json.load(io.open(os.path.join(SITE, 'scripts', 'category_texts.json'), encoding='utf-8'))
except Exception:
    cat_texts = {}
out_dir = os.path.join(SITE, 'category')
os.makedirs(out_dir, exist_ok=True)

for cat in cats:
    slug = slugify(cat)
    catf = 'ilike.*SFX' if cat == 'SFX' else f'eq.{urllib.parse.quote(cat)}'
    v = count_type(cat, 'video'); im = count_type(cat, 'image'); au = count_type(cat, 'audio')
    k = 'sfx' if cat == 'SFX' else kind(v, im, au); n = round50(v + im + au)
    items = requests.get(f"{BASE}/rest/v1/contents?select=id,title,thumbnail_url,preview_url,file_url,type&hidden=eq.false&category={catf}&order=created_at.desc&limit=36", headers=H, timeout=40).json()
    og_img = ''
    for x in items:
        u = x.get('thumbnail_url') or x.get('preview_url') or x.get('file_url')
        if u: og_img = u; break
    og_img = og_img or 'https://pixamedia.net/og-image.jpg'
    title = cat_title(cat, k); desc = cat_desc(cat, k, n)
    page = tpl
    page = re.sub(r'<title>.*?</title>', f'<title>{esc(title)}</title>', page, count=1)
    page = re.sub(r'<meta name="description" content="[^"]*">', f'<meta name="description" content="{esc(desc)}">', page, count=1)
    page = re.sub(r'<link rel="canonical" href="[^"]*">', f'<link rel="canonical" href="https://pixamedia.net/category/{slug}">', page, count=1)
    page = re.sub(r'<meta property="og:title" content="[^"]*">', f'<meta property="og:title" content="{esc(title)}">', page, count=1)
    page = re.sub(r'<meta property="og:description" content="[^"]*">', f'<meta property="og:description" content="{esc(desc)}">', page, count=1)
    page = re.sub(r'<meta property="og:url" content="[^"]*">', f'<meta property="og:url" content="https://pixamedia.net/category/{slug}">', page, count=1)
    page = re.sub(r'<meta property="og:image" content="[^"]*">', f'<meta property="og:image" content="{esc(og_img)}">', page, count=1)
    jsonld = ('<script type="application/ld+json">{"@context":"https://schema.org","@type":"CollectionPage","name":'+json.dumps(title)+',"description":'+json.dumps(desc)+',"url":"https://pixamedia.net/category/'+slug+'"}</script>'
              '<script type="application/ld+json">{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[{"@type":"ListItem","position":1,"name":"Home","item":"https://pixamedia.net/"},{"@type":"ListItem","position":2,"name":'+json.dumps(cat)+'}]}</script>')
    page = page.replace('</head>', jsonld + '</head>', 1)
    h1txt = cat_h1(cat, k)
    page = re.sub(r'(<h1[^>]*>).*?(</h1>)', lambda m: m.group(1) + esc(h1txt) + m.group(2), page, count=1, flags=re.S)
    intro = cat_texts.get(slug, '')
    if intro:
        page = re.sub(r'<p id="hero-sub"[^>]*>.*?</p>', '<p id="hero-sub" class="text-gray-400 text-sm sm:text-base mb-6">' + esc(intro) + '</p>', page, count=1, flags=re.S)
    cards = []
    for x in items:
        raw = x.get('title') or cat
        t = esc(raw)
        th = x.get('thumbnail_url') or x.get('preview_url') or ''
        alt = esc(f"{raw} - {cat} AI stock")
        img = f'<img src="{esc(th)}" alt="{alt}" loading="lazy" width="320" height="180" style="width:100%;height:100%;object-fit:cover">' if th else ('<i class="fa-solid fa-volume-high text-3xl text-purple-400/40"></i>' if k in ('audio', 'sfx') else '<i class="fa-solid fa-circle-play text-3xl text-white/30"></i>')
        xid = str(x.get('id') or '')
        aslug = slugify(raw) + ('-' + xid[-6:] if xid else '')
        apage = os.path.join(SITE, 'a', aslug, 'index.html')
        href = f'/a/{aslug}/' if os.path.exists(apage) else f'/category/{slug}'
        cards.append(f'<a href="{href}" class="asset-card lazy-card bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden flex flex-col h-64"><div class="flex-grow bg-gray-900 flex items-center justify-center relative overflow-hidden">{img}</div><div class="p-3 bg-gray-900 border-t border-gray-800/50"><h4 class="text-xs font-semibold truncate mt-1 text-gray-200">{t}</h4></div></a>')
    prerender = '<div class="prerender-cards grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4 mb-4">' + ''.join(cards) + '</div>'
    page = page.replace('<div id="asset-grid"', prerender + '<div id="asset-grid"', 1)
    init_js = ("<script>(function(){var pc=document.querySelector('.prerender-cards'); if(pc) pc.remove(); var m=location.pathname.match(/\\/category\\/([^\\/]+)/);if(m){var cat="+catmap+"[m[1]];if(cat){currentCat=cat;setTimeout(function(){var el=Array.from(document.querySelectorAll('.cat-card')).find(function(n){return cat!=='All'&&n.textContent.indexOf(cat)>=0})||document.getElementById('cat-all');filterCat(cat,el);},50);}}})();</script>")
    page = page.replace('</body>', init_js + '</body>', 1)
    dest = os.path.join(out_dir, slug, 'index.html')
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    io.open(dest, 'w', encoding='utf-8', newline='\n').write(page)
    print(f'  {slug:30} {k:13} gercek={v+im+au:5} n={n:6}')

print(f'\nUretilen sayfa: {len(cats)}')
