// ============================================================
// Gumroad Ping webhook — PixaMedia API tier otomatik aktivasyonu
// ============================================================
// Cloudflare Pages Function: /api/gumroad-ping (POST, form-encoded)
//
// Gerekli env değişkenleri (Cloudflare Pages -> Settings -> Variables/Secrets):
//   GUMROAD_PING_SECRET   : URL'deki ?secret=... ile eşleşen gizli token (ZORUNLU)
//   GUMROAD_PRODUCT_ID    : virgülle ayrılmış ürün id listesi (ZORUNLU)
//                           örn. "ttly8aIicN6hi8fhjXrhUA==,<abonelik-urun-id>"
//   GUMROAD_SELLER_ID     : satıcı user id (OPSİYONEL — tanımlıysa kontrol edilir)
//   SUPABASE_URL          : https://xxxx.supabase.co
//   SUPABASE_SERVICE_KEY  : service_role key (profiles + gumroad_pending yazma)
//
// Bu dosyada HİÇBİR gizli değer yoktur — tümü env'den okunur.

export async function onRequestPost(context) {
  const { request, env } = context;

  // 1) Gizli token kontrolü (URL query: ?secret=...)
  const url = new URL(request.url);
  const secret = url.searchParams.get("secret") || "";
  if (!env.GUMROAD_PING_SECRET || secret !== env.GUMROAD_PING_SECRET) {
    return json({ error: "unauthorized" }, 401);
  }

  // 2) Form-encoded gövde parse
  let body = {};
  try {
    body = Object.fromEntries(new URLSearchParams(await request.text()));
  } catch (e) {
    console.log("[gumroad-ping] body parse error:", e && e.message);
    return new Response("ok", { status: 200 }); // Gumroad tekrar denemesin
  }

  // 3) seller_id OPSİYONEL kontrol
  if (env.GUMROAD_SELLER_ID && body.seller_id !== env.GUMROAD_SELLER_ID) {
    console.log("[gumroad-ping] seller mismatch", { seller_id: body.seller_id });
    return json({ error: "forbidden" }, 403);
  }

  // 4) product_id kontrolü (virgülle ayrılmış çoklu)
  const allowed = String(env.GUMROAD_PRODUCT_ID || "")
    .split(",").map((s) => s.trim()).filter(Boolean);
  if (allowed.length > 0 && !allowed.includes(String(body.product_id || ""))) {
    console.log("[gumroad-ping] product mismatch", { product_id: body.product_id });
    return json({ error: "forbidden" }, 403);
  }

  const email = String(body.email || "").trim().toLowerCase();
  const sale_id = String(body.sale_id || "");
  const subscription_id = String(body.subscription_id || "");
  const is_cancelled = body.cancelled === "true" || body.ended === "true";
  const is_refunded = body.refunded === "true" || body.disputed === "true" || body.failed === "true";

  console.log("[gumroad-ping] received", { email, sale_id, subscription_id, cancelled: is_cancelled, refunded: is_refunded, test: body.test });

  if (!email) {
    console.log("[gumroad-ping] email yok — yok sayildi");
    return new Response("ok", { status: 200 });
  }

  // İptal/bitiş/iade -> registered'a düşür; satış/yenileme -> api yap
  const newTier = (is_cancelled || is_refunded) ? "registered" : "api";

  const supabaseHeaders = {
    "apikey": env.SUPABASE_SERVICE_KEY,
    "Authorization": `Bearer ${env.SUPABASE_SERVICE_KEY}`,
    "Content-Type": "application/json",
  };

  try {
    // 5) E-postası eşleşen profili bul (email zaten lowercase)
    const findRes = await fetch(
      `${env.SUPABASE_URL}/rest/v1/profiles?email=eq.${encodeURIComponent(email)}&select=id,tier&limit=1`,
      { headers: supabaseHeaders }
    );
    const rows = await findRes.json();

    if (Array.isArray(rows) && rows.length > 0) {
      // Profil var -> tier güncelle
      const profileId = rows[0].id;
      const upd = await fetch(
        `${env.SUPABASE_URL}/rest/v1/profiles?id=eq.${profileId}`,
        {
          method: "PATCH",
          headers: { ...supabaseHeaders, "Prefer": "return=minimal" },
          body: JSON.stringify({ tier: newTier }),
        }
      );
      console.log("[gumroad-ping] tier guncellendi", { email, id: profileId, tier: newTier, http: upd.status });
    } else {
      // Profil yok -> gumroad_pending'e yaz (hesap açılınca trigger aktif eder)
      const ins = await fetch(
        `${env.SUPABASE_URL}/rest/v1/gumroad_pending`,
        {
          method: "POST",
          headers: { ...supabaseHeaders, "Prefer": "return=minimal" },
          body: JSON.stringify({
            email,
            sale_id: sale_id || null,
            subscription_id: subscription_id || null,
            tier: newTier,
          }),
        }
      );
      console.log("[gumroad-ping] profil yok -> gumroad_pending'e yazildi", { email, tier: newTier, http: ins.status });
    }
  } catch (e) {
    console.log("[gumroad-ping] supabase hatasi:", e && e.message);
    return new Response("ok", { status: 200 });
  }

  // 6) Her zaman 200 (idempotent; aynı sale_id tekrar gelirse tier aynı kalır)
  return new Response("ok", { status: 200 });
}

export async function onRequestGet(context) {
  return json({ error: "method not allowed" }, 405);
}

function json(obj, status) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "content-type": "application/json" },
  });
}

