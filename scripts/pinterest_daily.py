#!/usr/bin/env python3
# Pinterest gunluk pin + RSS (CANLI)
import json, re, os, io, subprocess, sys, time, requests, struct
from datetime import datetime, date
from email.utils import format_datetime
from PIL import Image, ImageDraw, ImageFont
import piexif

N = 10
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP_DIR = os.path.join(BASE, 'scripts', 'pins_tmp')
STATE_FILE = os.path.join(BASE, 'scripts', 'pinterest_state.json')
SEL_FILE = os.path.join(BASE, 'scripts', 'asset_pages_selected.json')
FEED_FILE = os.path.join(BASE, 'pinterest-coloring.xml')
LOCK_FILE = os.path.join(BASE, 'scripts', 'pinterest.lock')
CONFIG_FILE = r'c:\Users\User\Desktop\pixamedia-bot\config.json'
LOG_FILE = r'c:\Users\User\Desktop\cline\pinterest_log.txt'

def slugify(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')

def logline(msg):
    line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | {msg}"
    print(line)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')

XMP_DST = ('<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
           '<rdf:Description rdf:about="" xmlns:Iptc4xmpExt="http://iptc.org/std/Iptc4xmpExt/2008-02-29/" xmlns:dc="http://purl.org/dc/elements/1.1/">'
           '<Iptc4xmpExt:DigitalSourceType>http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia</Iptc4xmpExt:DigitalSourceType>'
           '<dc:creator><rdf:Seq><rdf:li>PixaMedia.net AI-generated</rdf:li></rdf:Seq></dc:creator>'
           '<dc:source>PixaMedia.net AI-generated</dc:source>'
           '</rdf:Description></rdf:RDF></x:xmpmeta>')

def add_ai_meta(jpeg_bytes):
    try:
        exif_dict = {'0th': {piexif.ImageIFD.Artist: b'PixaMedia.net AI-generated',
                             piexif.ImageIFD.ImageDescription: b'PixaMedia.net AI-generated'},
                     'Exif': {}, 'GPS': {}, '1st': {}, 'thumbnail': None}
        jpeg_bytes = piexif.insert(piexif.dump(exif_dict), jpeg_bytes)
    except Exception:
        pass
    header = b'http://ns.adobe.com/xap/1.0/\x00'
    xmp = XMP_DST.encode('utf-8')
    seg = b'\xff\xe1' + struct.pack('>H', len(header) + len(xmp) + 2) + header + xmp
    return jpeg_bytes[:2] + seg + jpeg_bytes[2:]


# --- kalite filtresi (bos/seyrek resim) ---
MIN_INK_RATIO = 0.040
MAX_BBOX_COVER = 0.700
MIN_GRID_CELLS = 0

def quality_metrics(img_bytes):
    im = Image.open(io.BytesIO(img_bytes)).convert('L')
    im = im.resize((400, int(im.height * 400 / im.width)), Image.LANCZOS)
    w, h = im.size
    px = im.load()
    dark = [(x, y) for y in range(h) for x in range(w) if px[x, y] < 128]
    ink = len(dark) / (w * h)
    if not dark:
        return {'ink': 0.0, 'bbox': 0.0, 'grid': 0}
    xs = [p[0] for p in dark]; ys = [p[1] for p in dark]
    m = 0.03
    x0, x1 = int(w * m), int(w * (1 - m)); y0, y1 = int(h * m), int(h * (1 - m))
    xs2 = [x for x in xs if x0 <= x < x1]; ys2 = [y for y in ys if y0 <= y < y1]
    if xs2:
        bw = max(xs2) - min(xs2) + 1; bh = max(ys2) - min(ys2) + 1
        bbox = (bw * bh) / (w * h)
    else:
        bbox = 0.0
    cells = 0
    for gy in range(4):
        for gx in range(4):
            cnt = sum(1 for y in range(gy * h // 4, (gy + 1) * h // 4)
                      for x in range(gx * w // 4, (gx + 1) * w // 4) if px[x, y] < 128)
            if cnt > (w * h) // 16 * 0.005:
                cells += 1
    return {'ink': round(ink, 4), 'bbox': round(bbox, 4), 'grid': cells}

def passes_quality(q):
    if q['ink'] < MIN_INK_RATIO and q['bbox'] > MAX_BBOX_COVER:
        return False
    if q['grid'] < MIN_GRID_CELLS:
        return False
    return True


if os.path.exists(LOCK_FILE):
    age = time.time() - os.path.getmtime(LOCK_FILE)
    if age < 2 * 3600:
        logline('DUR: baska kopya calisiyor (kilit 2 saatten yeni)')
        sys.exit(1)
    else:
        os.remove(LOCK_FILE)
open(LOCK_FILE, 'w').write(str(os.getpid()))

try:
    cfg = json.load(open(CONFIG_FILE, encoding='utf-8'))
    SUP_URL = cfg['supabase_url'].rstrip('/'); SUP_KEY = cfg['supabase_key']
    H = {'apikey': SUP_KEY, 'Authorization': 'Bearer ' + SUP_KEY}

    state = json.load(open(STATE_FILE, encoding='utf-8')) if os.path.exists(STATE_FILE) else {'pinned_ids': [], 'pinned': [], 'last_run_date': '', 'rejected': []}
    state.setdefault('rejected', [])
    if state.get('last_run_date') == date.today().isoformat():
        logline('bugun zaten calisti, cikiliyor')
        os.remove(LOCK_FILE)
        sys.exit(0)

    rows = []
    for off in range(0, 200000, 1000):
        r = requests.get(f"{SUP_URL}/rest/v1/contents?select=id,title,file_url,is_sandbox_sample,created_at&hidden=eq.false&category=eq.Coloring Pages&order=created_at.desc&limit=1000&offset={off}", headers=H, timeout=60)
        b = r.json()
        if not b:
            break
        rows.extend(b)
        if len(b) < 1000:
            break
    rows = [x for x in rows if not x.get('is_sandbox_sample') and len((x.get('title') or '').strip()) >= 3]
    logline(f'coloring aday: {len(rows)}')

    pinned = set(state.get('pinned_ids', []))
    rejected_ids = {str(r.get('id')) for r in state.get('rejected', [])}
    sel = json.load(open(SEL_FILE, encoding='utf-8')) if os.path.exists(SEL_FILE) else {}
    sel_ids = {str(e.get('id')) for e in sel.values() if e.get('category') == 'Coloring Pages'}
    pilot = [x for x in rows if str(x.get('id')) in sel_ids]
    others = [x for x in rows if str(x.get('id')) not in sel_ids]
    candidates = [x for x in (pilot + others) if str(x.get('id')) not in pinned and str(x.get('id')) not in rejected_ids]
    picks = []
    checked = 0
    for x in candidates:
        if checked >= 80:
            break
        checked += 1
        try:
            q = quality_metrics(requests.get(x['file_url'], timeout=30).content)
        except Exception as e:
            logline(f'ATLA (gorsel indirilemedi): {x.get("title")[:40]} {e}')
            continue
        if not passes_quality(q):
            state['rejected'].append({'id': str(x.get('id')), 'title': x.get('title'), **q})
            logline(f'RED (seyrek): {x.get("title")[:40]} ink={q["ink"]} bbox={q["bbox"]} grid={q["grid"]}/16')
            continue
        picks.append(x)
        if len(picks) >= N:
            break
    logline(f'secilecek pin: {len(picks)} (kontrol edilen aday: {checked})')

    def get_font(size):
        for p in ['C:/Windows/Fonts/arial.ttf', 'C:/Windows/Fonts/segoeui.ttf']:
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
        return ImageFont.load_default()

    def make_pin(x):
        title = (x.get('title') or '').strip().replace('Coloring Page — ', '').replace('Coloring Page - ', '')
        if len(title) > 55:
            title = title[:52].rstrip() + '...'
        img = Image.open(io.BytesIO(requests.get(x['file_url'], timeout=30).content)).convert('RGB')
        W, H = 1000, 1500
        canvas = Image.new('RGB', (W, H), 'white')
        d = ImageDraw.Draw(canvas)
        ratio = 1000 / img.width
        nh = int(img.height * ratio)
        if nh > 1350:
            nh = 1350; nw = int(img.width * (nh / img.height))
        else:
            nw = 1000
        canvas.paste(img.resize((nw, nh), Image.LANCZOS), ((W - nw) // 2, 80))
        f1 = get_font(36)
        tw = d.textlength(title, font=f1) if hasattr(d, 'textlength') else len(title) * 18
        d.text(((W - tw) // 2, 20), title, fill='black', font=f1)
        f2 = get_font(28)
        fw = d.textlength('pixamedia.net', font=f2) if hasattr(d, 'textlength') else 140
        d.text(((W - fw) // 2, H - 45), 'pixamedia.net', fill='black', font=f2)
        return canvas

    os.makedirs(TMP_DIR, exist_ok=True)


    def r2_upload(local, key):
        cmd = [sys.executable, '-m', 'awscli', 's3', 'cp', local, f"s3://{cfg['r2_bucket']}/pins/{key}",
               '--endpoint-url', f"https://{cfg['r2_account_id']}.r2.cloudflarestorage.com"]
        env = os.environ.copy()
        env['AWS_ACCESS_KEY_ID'] = cfg['r2_access_key']
        env['AWS_SECRET_ACCESS_KEY'] = cfg['r2_secret_key']
        env['AWS_DEFAULT_REGION'] = 'auto'
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=env)
        return r.returncode == 0

    new_items = []
    for x in picks:
        title = (x.get('title') or '').strip()
        sid = str(x.get('id') or '')
        slug = slugify(title) + '-' + sid[-6:]
        local = os.path.join(TMP_DIR, slug + '.jpg')
        img = make_pin(x)
        q = 85
        while True:
            buf = io.BytesIO()
            img.save(buf, 'JPEG', quality=q, optimize=True)
            if buf.tell() < 1_000_000 or q <= 60:
                break
            q -= 5
        open(local, 'wb').write(add_ai_meta(buf.getvalue()))
        if not r2_upload(local, slug + '.jpg'):
            logline(f'ATLA (R2 yuklenemedi): {slug}')
            continue
        url = f"https://cdn.pixamedia.net/pins/{slug}.jpg"
        ok = False
        for _ in range(3):
            try:
                rr = requests.head(url, timeout=20, allow_redirects=True)
                if rr.status_code == 200 and 'image/jpeg' in (rr.headers.get('content-type') or ''):
                    ok = True; break
            except Exception:
                pass
            time.sleep(3)
        if not ok:
            logline(f'ATLA (dogrulanamadi): {url}')
            continue
        new_items.append({'id': sid, 'title': title, 'slug': slug, 'bytes': os.path.getsize(local), 'ai': True})
        logline(f'YUKLENDI: {slug} ({os.path.getsize(local)} bayt)')
    logline(f'basariyla yuklenen: {len(new_items)}')

    if new_items:
        # d) asset_pages_selected.json'a ekle + build
        for it in new_items:
            sel[it['slug']] = {'slug': it['slug'], 'id': it['id'], 'title': it['title'], 'category': 'Coloring Pages',
                               'type': 'image', 'file_url': f"https://cdn.pixamedia.net/pins/{it['slug']}.jpg",
                               'thumbnail_url': '', 'preview_url': '', 'quality': 'A4', 'format': 'vertical', 'created_at': ''}
        json.dump(sel, open(SEL_FILE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        subprocess.run([sys.executable, os.path.join(BASE, 'scripts', 'build_assets.py')], cwd=BASE, timeout=600)
        subprocess.run([sys.executable, os.path.join(BASE, 'scripts', 'build_post.py')], cwd=BASE, timeout=300)
        logline('build_assets + build_post tamam')

    # e) RSS repo kokune (son 30)
    state['pinned_ids'] = sorted(pinned | {it['id'] for it in new_items})
    state['pinned'] = (state.get('pinned') or []) + new_items
    state['last_run_date'] = date.today().isoformat()
    state['last_run_ok'] = True
    state['last_added'] = len(new_items)
    json.dump(state, open(STATE_FILE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    recent = (state.get('pinned') or [])[-30:]
    def rss_item(it):
        t = it['title'].replace('Coloring Page — ', '').replace('Coloring Page - ', '')
        ft = f"Free Printable {t} Coloring Page"[:100]
        link = f"https://pixamedia.net/a/{it['slug']}/"
        desc = (f"Free printable {it['title'].lower()} coloring page (AI-generated) for kids and adults. Download and print more at pixamedia.net"
                if it.get('ai') else
                f"Free printable {it['title'].lower()} coloring page for kids and adults. Download and print more at pixamedia.net")
        enc = f"https://cdn.pixamedia.net/pins/{it['slug']}.jpg"
        pub = format_datetime(datetime.now())
        return (f"  <item><title>{ft}</title><link>{link}</link><description>{desc}</description>"
                f"<enclosure url=\"{enc}\" length=\"{it['bytes']}\" type=\"image/jpeg\"/>"
                f"<guid isPermaLink=\"true\">{link}</guid><pubDate>{pub}</pubDate></item>")
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<rss version="2.0"><channel><title>PixaMedia Coloring Pages</title>'
           '<link>https://pixamedia.net/</link><description>Free printable coloring pages for kids and adults.</description>\n'
           + '\n'.join(rss_item(i) for i in recent) + '\n</channel></rss>\n')
    open(FEED_FILE, 'w', encoding='utf-8').write(xml)

    # g) git
    os.chdir(BASE)
    subprocess.run(['git', 'pull', '--rebase', 'origin', 'main'], capture_output=True, text=True, timeout=120)
    st = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True, timeout=60).stdout
    changed = [l.split()[-1] for l in st.splitlines() if l.strip()]
    logline(f'git degisen dosya: {len(changed)}')
    for c in changed[:40]:
        logline(f'  {c}')
    add = ['a/', 'sitemap.xml', 'scripts/asset_pages_selected.json', 'pinterest-coloring.xml', 'scripts/pinterest_state.json']
    subprocess.run(['git', 'add'] + add, timeout=60)
    rc = subprocess.run(['git', 'commit', '-m', f'Pinterest: daily feed +{len(new_items)}'], capture_output=True, text=True, timeout=60)
    subprocess.run(['git', 'push', 'origin', 'main'], capture_output=True, text=True, timeout=120)
    logline(f'git commit/push yapildi (+{len(new_items)})')

    # h) 90 sn bekle + dogrula
    time.sleep(90)
    try:
        fr = requests.get('https://pixamedia.net/pinterest-coloring.xml', timeout=30)
        logline(f'feed: {fr.status_code} | item={fr.text.count("<item>")}')
    except Exception as e:
        logline(f'feed kontrol hata: {e}')
    if new_items:
        first = new_items[0]
        for u in [f"https://pixamedia.net/a/{first['slug']}/", f"https://cdn.pixamedia.net/pins/{first['slug']}.jpg"]:
            try:
                rr = requests.head(u, timeout=20, allow_redirects=True)
                logline(f'  {u} -> {rr.status_code}')
            except Exception as e:
                logline(f'  {u} -> hata {e}')

    # i) IndexNow (best-effort)
    try:
        import urllib.parse
        key = 'aadf6872a68085f5e90edf98e734d4c2'
        new_urls = [f"https://pixamedia.net/a/{it['slug']}/" for it in new_items]
        payload = {'host': 'pixamedia.net', 'key': key, 'keyLocation': f'https://pixamedia.net/{key}.txt', 'urlList': new_urls}
        r = requests.post('https://api.indexnow.org/indexnow', json=payload, timeout=30)
        logline(f'IndexNow: {r.status_code} {r.text[:100]}')
    except Exception as e:
        logline(f'IndexNow hata (yok sayildi): {e}')

    logline('TAMAMLANDI +' + str(len(new_items)))
    for f in os.listdir(TMP_DIR):
        try:
            os.remove(os.path.join(TMP_DIR, f))
        except Exception:
            pass
except Exception as e:
    logline('HATA: ' + repr(e))
finally:
    if os.path.exists(LOCK_FILE):
        try:
            os.remove(LOCK_FILE)
        except Exception:
            pass

