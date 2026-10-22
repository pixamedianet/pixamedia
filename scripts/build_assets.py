#!/usr/bin/env python3
import io, re, os, json
from html import escape as esc
SITE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def slugify(s): return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')

sel = json.load(open(os.path.join(SITE, 'scripts', 'asset_pages_selected.json'), encoding='utf-8'))
entries = list(sel.values())
by_cat = {}
for e in entries:
    by_cat.setdefault(e['category'], []).append(e)

TPL = io.open(os.path.join(SITE, 'scripts', 'template_asset.html'), encoding='utf-8').read()

def trunc_title(title, kind):
    suf = ' - Free 4K AI ' + kind + ' | PixaMedia'
    max_t = 65 - len(suf)
    t = title
    if len(t) > max_t:
        t = t[:max_t-1].rstrip() + '...'
    return (t + suf)[:65]

def make_desc(e):
    t = e['title']
    res = e.get('quality') or '4K'
    base = f"{t} - {e['category']} {res} AI image. Free download for YouTube, social media and personal projects."
    if len(base) < 140:
        base = f"Download {t}, a {e['category']} {res} AI-generated image. Free for YouTube, Shorts, TikTok and personal projects, no watermark."
    return base[:155]

out_dir = os.path.join(SITE, 'a')
os.makedirs(out_dir, exist_ok=True)
made = 0
for e in entries:
    if e.get('hidden'):
        continue
    cat = e['category']
    kind = 'Coloring Page' if cat == 'Coloring Pages' else 'Image'
    res = e.get('quality') or ('A4' if cat == 'Coloring Pages' else '4K')
    date = (e.get('created_at') or '')[:10]
    img = e.get('file_url') or e.get('thumbnail_url') or e.get('preview_url') or ''
    if not img:
        continue
    url = f'https://pixamedia.net/a/{e["slug"]}/'
    title = trunc_title(e['title'], kind)
    desc = make_desc(e)
    catslug = slugify(cat)
    sims = [x for x in by_cat.get(cat, []) if x['slug'] != e['slug']][:8]
    similar = ''.join(
        '<a href="/a/%s/" style="background:#0f172a;border:1px solid #1e293b;border-radius:12px;overflow:hidden;display:block">'
        '<img src="%s" alt="%s" loading="lazy" width="300" height="300" style="width:100%%;display:block">'
        '<div style="padding:8px;font-size:12px;color:#e5e7eb;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">%s</div></a>'
        % (x['slug'], esc(x.get('file_url') or x.get('thumbnail_url') or ''), esc(x['title']), esc(x['title']))
        for x in sims
    )
    jsonld = json.dumps({
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "BreadcrumbList", "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home", "item": "https://pixamedia.net/"},
                {"@type": "ListItem", "position": 2, "name": cat, "item": f"https://pixamedia.net/category/{catslug}/"},
                {"@type": "ListItem", "position": 3, "name": e['title']}]},
            {"@type": "ImageObject", "contentUrl": img, "thumbnailUrl": e.get('thumbnail_url') or img,
             "name": e['title'], "description": desc,
             "creator": {"@type": "Organization", "name": "PixaMedia"},
             "license": "https://pixamedia.net/terms",
             "acquireLicensePage": "https://pixamedia.net/api"}
        ]
    })
    page = TPL.format(title=esc(title), desc=esc(desc), url=url, img=esc(img),
                      jsonld='<script type="application/ld+json">' + jsonld + '</script>',
                      cat=esc(cat), catslug=catslug, kind=kind, res=esc(res), date=date, similar=similar)
    dest = os.path.join(out_dir, e['slug'], 'index.html')
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    io.open(dest, 'w', encoding='utf-8', newline='\n').write(page)
    made += 1

print('uretilen /a/ sayfasi:', made)
