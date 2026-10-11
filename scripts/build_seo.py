#!/usr/bin/env python3
import io, re, os, json, urllib.parse, datetime, requests
from html import escape as esc
SITE = r'c:\Users\User\Desktop\Reels Otomatik\pixamedia-site'
BASE = 'https://qxawiooxixrkhjauibxw.supabase.co'
KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InF4YXdpb294aXhya2hqYXVpYnh3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzk4MjczMTYsImV4cCI6MjA5NTQwMzMxNn0.UfDPc-_tr45TbN9eZace4g9Sy5_1vqMGbbSit_VutKM'
H = {'apikey': KEY, 'Authorization': 'Bearer ' + KEY}

def slugify(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')

def count_of(cat):
    r = requests.head(f"{BASE}/rest/v1/contents?select=id&category=eq.{urllib.parse.quote(cat)}", headers={**H, 'Prefer': 'count=exact'}, timeout=30)
    cr = r.headers.get('content-range', '')
    return int(cr.split('/')[-1]) if '/' in cr else 0

def cat_title(cat):
    if cat == 'Music': return 'Free AI Music & Audio Stock | PixaMedia'
    if cat == 'Coloring Pages': return 'Free Coloring Pages for Kids | PixaMedia'
    return f"Free 4K {cat} Stock Assets | PixaMedia"[:60]

def cat_desc(cat, count):
    if cat == 'Music':
        d = f"Browse {count}+ AI-generated music tracks. Watermark-free. 2 free downloads per day."
    elif cat == 'Coloring Pages':
        d = f"Browse {count}+ printable coloring pages for kids. Watermark-free. 2 free downloads per day."
    else:
        d = f"Browse {count}+ AI-generated {cat.lower()} videos and images in 4K/8K. Watermark-free. 2 free downloads per day."
    return d[:157] + '...' if len(d) > 160 else d

tpl = io.open(os.path.join(SITE, 'index.html'), encoding='utf-8').read()
cats = [c for c in re.findall(r"filterCat\('([^']+)',this\)", tpl) if c != 'All']
slugs = {}
for c in cats: slugs.setdefault(slugify(c), []).append(c)
out_dir = os.path.join(SITE, 'category')
os.makedirs(out_dir, exist_ok=True)
catmap = json.dumps({slugify(c): c for c in cats})

for cat in cats:
    slug = slugify(cat)
    count = count_of(cat)
    items = requests.get(f"{BASE}/rest/v1/contents?select=title,thumbnail_url,preview_url,file_url&category=eq.{urllib.parse.quote(cat)}&order=created_at.desc&limit=48", headers=H, timeout=30).json()
    og_img = ''
    for x in items:
        u = x.get('thumbnail_url') or x.get('preview_url') or x.get('file_url')
        if u: og_img = u; break
    og_img = og_img or 'https://pixamedia.net/og-image.jpg'
    title = cat_title(cat); desc = cat_desc(cat, count)
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
    h1txt = 'Free AI Music & Audio Stock' if cat == 'Music' else ('Free Coloring Pages for Kids' if cat == 'Coloring Pages' else f'Free 4K {cat} Stock Assets')
    page = re.sub(r'(<h1[^>]*>).*?(</h1>)', lambda m: m.group(1) + esc(h1txt) + m.group(2), page, count=1, flags=re.S)
    cards = []
    for x in items:
        t = esc(x.get('title') or cat)
        th = x.get('thumbnail_url') or x.get('preview_url') or ''
        alt = esc(f"{x.get('title') or cat} - {cat} AI stock")
        img = f'<img src="{esc(th)}" alt="{alt}" loading="lazy" width="320" height="180" style="width:100%;height:100%;object-fit:cover">' if th else '<i class="fa-solid fa-circle-play text-3xl text-white/30"></i>'
        cards.append(f'<a href="/category/{slug}" class="asset-card lazy-card bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden flex flex-col h-64"><div class="flex-grow bg-gray-900 flex items-center justify-center relative overflow-hidden">{img}</div><div class="p-3 bg-gray-900 border-t border-gray-800/50"><h4 class="text-xs font-semibold truncate mt-1 text-gray-200">{t}</h4></div></a>')
    prerender = '<div class="prerender-cards grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4 mb-4">' + ''.join(cards) + '</div>'
    page = page.replace('<div id="asset-grid"', prerender + '<div id="asset-grid"', 1)
    init_js = ("<script>(function(){var pc=document.querySelector('.prerender-cards'); if(pc) pc.remove(); var m=location.pathname.match(/\\/category\\/([^\\/]+)/);if(m){var cat="+catmap+"[m[1]];if(cat){currentCat=cat;setTimeout(function(){var el=Array.from(document.querySelectorAll('.cat-card')).find(function(n){return cat!=='All'&&n.textContent.indexOf(cat)>=0})||document.getElementById('cat-all');filterCat(cat,el);},50);}}})();</script>")
    page = page.replace('</body>', init_js + '</body>', 1)
    dest = os.path.join(out_dir, slug, 'index.html')
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    io.open(dest, 'w', encoding='utf-8').write(page)
    print(f'  {slug:34} count={count:5}')

print(f'\nUretilen sayfa: {len(cats)}')
print('slug cakismasi:', {k: v for k, v in slugs.items() if len(v) > 1})
