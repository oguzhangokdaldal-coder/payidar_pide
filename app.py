import hmac
import os
import secrets
from datetime import datetime, timedelta
from datetime import time as dtime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for

import paytr
import webhooks
from models import Campaign, Order, OrderItem, Product, Setting, ToplineMessage, db

# .env'in yolunu açıkça belirtiyoruz (app.py ile aynı klasörde) — bazı WSGI
# ortamlarında load_dotenv()'in parametresiz haliyle dosyayı otomatik bulması
# güvenilir olmuyor.
load_dotenv(Path(__file__).resolve().parent / ".env")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-degistir")
os.makedirs(app.instance_path, exist_ok=True)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "sqlite:///" + os.path.join(app.instance_path, "payidar.db")
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

app.config["PAYTR_MERCHANT_ID"] = os.environ.get("PAYTR_MERCHANT_ID", "")
app.config["PAYTR_MERCHANT_KEY"] = os.environ.get("PAYTR_MERCHANT_KEY", "")
app.config["PAYTR_MERCHANT_SALT"] = os.environ.get("PAYTR_MERCHANT_SALT", "")
app.config["PAYTR_TEST_MODE"] = os.environ.get("PAYTR_TEST_MODE", "1") == "1"
app.config["ADMIN_PASSWORD"] = os.environ.get("ADMIN_PASSWORD", "")

app.config["WHATSAPP_WEBHOOK_URL"] = os.environ.get("WHATSAPP_WEBHOOK_URL", "")
app.config["WHATSAPP_WEBHOOK_SECRET"] = os.environ.get("WHATSAPP_WEBHOOK_SECRET", "")

ORDER_RATE_LIMIT_WINDOW_MIN = 15

# Çalışma saatleri: varsayılan olarak .env'deki OPENING_TIME / CLOSING_TIME
# ("SA:DK") kullanılır, ayarlanmamışsa 10:00–22:00. Yönetim panelinden
# (/admin/ayarlar) kaydedilen değer varsa .env'dekini geçersiz kılar — bu
# sayede saatler kod/sunucu değişikliği gerekmeden panelden güncellenebilir.
TR_TZ = ZoneInfo("Europe/Istanbul")


def _parse_hhmm(value, fallback):
    try:
        h, m = value.split(":")
        return dtime(int(h), int(m))
    except (ValueError, AttributeError, TypeError):
        return fallback


DEFAULT_OPENING_TIME = _parse_hhmm(os.environ.get("OPENING_TIME"), dtime(10, 0))
DEFAULT_CLOSING_TIME = _parse_hhmm(os.environ.get("CLOSING_TIME"), dtime(22, 0))


def get_setting(key, default=None):
    row = Setting.query.get(key)
    return row.value if row else default


def set_setting(key, value):
    row = Setting.query.get(key)
    if row:
        row.value = value
    else:
        row = Setting(key=key, value=value)
        db.session.add(row)
    db.session.commit()


def get_working_hours():
    opening = _parse_hhmm(get_setting("opening_time"), DEFAULT_OPENING_TIME)
    closing = _parse_hhmm(get_setting("closing_time"), DEFAULT_CLOSING_TIME)
    return opening, closing


def is_force_closed():
    """Yönetim panelindeki 'Şu an kapalıyız' anahtarı — saat ne olursa olsun
    (tatil, malzeme bitmesi, ara verme vb.) siparişi tamamen durdurur."""
    return get_setting("force_closed") == "1"


def is_shop_open(now=None):
    """Şu an (Türkiye saatiyle) çalışma saatleri içinde miyiz?"""
    if is_force_closed():
        return False
    opening, closing = get_working_hours()
    current = (now or datetime.now(TR_TZ)).time()
    if opening <= closing:
        return opening <= current < closing
    # Gece yarısını geçen çalışma saatleri (örn. 18:00–02:00) için.
    return current >= opening or current < closing

# Sipariş durum akışı: her durumdan hangi durumlara geçilebileceği.
# "onay_bekliyor" -> alındı ya da iptal; alındı -> hazırlanıyor ya da iptal; ...
ORDER_STATUS_LABELS = {
    "onay_bekliyor": "Onay Bekliyor",
    "alindi": "Alındı",
    "hazirlaniyor": "Hazırlanıyor",
    "yolda": "Dağıtıma Çıktı",
    "teslim_edildi": "Teslim Edildi",
    "iptal": "İptal Edildi",
}
ORDER_STATUS_TRANSITIONS = {
    "onay_bekliyor": ["alindi", "iptal"],
    "alindi": ["hazirlaniyor", "iptal"],
    "hazirlaniyor": ["yolda", "iptal"],
    "yolda": ["teslim_edildi", "iptal"],
    "teslim_edildi": [],
    "iptal": [],
}
# Yönetim panelinde her durum kendi sütununda ayrı ayrı gösterilir, sırası bu.
ORDER_STATUS_COLUMNS = ["onay_bekliyor", "alindi", "hazirlaniyor", "yolda", "teslim_edildi", "iptal"]

# Teslimat yapılan mahalleler: her birinin minimum sepet tutarı (₺) ve yaklaşık
# konumu (tarayıcı konumundan en yakın mahalleyi otomatik seçmek için).
# checkout.html'deki <option> listesiyle senkron tutulmalı.
DELIVERY_ZONES = [
    {"slug": "cunur", "name": "Çünür", "min_order": 500, "lat": 37.8150, "lng": 30.5452},
    {"slug": "mehmet-tonge", "name": "Mehmet Tönge", "min_order": 800, "lat": 37.8217, "lng": 30.5135},
    {"slug": "akkent", "name": "Akkent", "min_order": 1100, "lat": 37.8239, "lng": 30.5776},
    {"slug": "dogu-kampus", "name": "Doğu Kampüs", "min_order": 600, "lat": 37.8280, "lng": 30.5350},
]
DELIVERY_ZONES_BY_SLUG = {z["slug"]: z for z in DELIVERY_ZONES}
PICKUP_ADDRESS_LABEL = "Gel Al — mağazadan teslim alınacak"

# Aşağıdaki üç liste yalnızca İLK ÇALIŞTIRMADA (tablolar boşsa) veritabanına
# tohum olarak yazılır — menü/kampanya/bant artık koddan değil, yönetim
# panelinden (/admin/menu, /admin/kampanyalar, /admin/bant) düzenleniyor.
_SEED_PRODUCTS = [
    {"category": "pide", "name": "Özel Karışık Pide", "description": "Kuşbaşı, kaşar, sucuk ve közlenmiş biber", "price": 250, "tag": "Favori", "image": "img/karısik_pizza.jpg"},
    {"category": "pide", "name": "Kuşbaşılı Kaşarlı Pide", "description": "Zırh kıyması, bol kaşar ve tereyağı", "price": 200, "tag": "Yeni", "image": "img/kusbasi_kasar.jpg"},
    {"category": "pide", "name": "Kıymalı Pide", "description": "İnce kıyma, domates, biber ve maydanoz", "price": 150, "tag": "", "image": "img/kiymali.jpg"},
    {"category": "pide", "name": "Kaşarlı Pide", "description": "Uzayan kaşar, tereyağı ve çıtır hamur", "price": 160, "tag": "", "image": "img/kasarlipide.jpg"},
    {"category": "pide", "name": "Sucuklu Kaşarlı Pide", "description": "Baharatlı sucuk ve bol kaşar", "price": 250, "tag": "", "image": "img/sucuklu_kasar.jpg"},
    {"category": "pide", "name": "Lahmacun", "description": "İnce açılmış hamur, bol malzeme, taş fırında", "price": 140, "tag": "", "image": "img/lahmacun.jpg"},
    {"category": "pide", "name": "Peynirli Pide", "description": "Bol beyaz peynir ve maydanoz", "price": 150, "tag": "", "image": "img/peynirli_pide.jpg"},
    {"category": "pide", "name": "Kıymalı Kaşarlı Pide", "description": "İnce kıyma ve bol kaşar bir arada", "price": 170, "tag": "", "image": "img/kiymali_kasarli_pide.jpg"},
    {"category": "pide", "name": "Kuşbaşılı Pide", "description": "Zırh kuşbaşı, domates ve biber", "price": 180, "tag": "", "image": "img/kusbasili_pide.jpg"},
    {"category": "pide", "name": "Sade Kıymalı Pide", "description": "Bol kıyma, sade ve doyurucu", "price": 250, "tag": "", "image": "img/sade_kiymali_pide.jpg"},
    {"category": "izgara", "name": "Şiş Köfte", "description": "Izgara ateşinde közlenmiş şiş köfte", "price": 300, "tag": "", "image": "img/sis_kofte.jpg"},
    {"category": "izgara", "name": "Adana Kebap", "description": "Zırhta çekilmiş acılı et, köz sebzeler ve lavaş", "price": 300, "tag": "", "image": "img/adana_veya_urfa.jpg"},
    {"category": "izgara", "name": "Izgara Köfte", "description": "El yapımı ızgara köfte", "price": 300, "tag": "", "image": "img/izgara_kofte.jpg"},
    {"category": "izgara", "name": "Tavuk Şiş", "description": "Marine edilmiş tavuk şiş", "price": 300, "tag": "", "image": "img/tavuk_sis.jpg"},
    {"category": "durum", "name": "Adana Dürüm", "description": "Adana kebap, lavaş içinde sarılır", "price": 300, "tag": "", "image": "img/adana_durum.jpg"},
    {"category": "durum", "name": "Tavuk Dürüm", "description": "Marine tavuk şiş, lavaş içinde sarılır", "price": 300, "tag": "", "image": "img/tavuk_durum.jpg"},
    {"category": "durum", "name": "Şiş Köfte Dürüm", "description": "Şiş köfte, lavaş içinde sarılır", "price": 300, "tag": "", "image": ""},
    {"category": "icecek", "name": "Yayık Ayran", "description": "Günlük yoğurttan, buz gibi", "price": 45, "tag": "", "image": "img/ayran.jpg"},
    {"category": "icecek", "name": "Kutu Kola", "description": "330 ml, buz gibi", "price": 40, "tag": "", "image": "img/kutu_kola.jpg"},
    {"category": "icecek", "name": "Fanta", "description": "330 ml, buz gibi", "price": 40, "tag": "", "image": "img/fanta.jpg"},
    {"category": "icecek", "name": "Sprite", "description": "330 ml, buz gibi", "price": 40, "tag": "", "image": "img/sprite.jpg"},
    {"category": "icecek", "name": "Soda", "description": "200 ml, sade", "price": 25, "tag": "", "image": ""},
    {"category": "icecek", "name": "Şalgam Suyu", "description": "Acılı, geleneksel usul", "price": 35, "tag": "", "image": "img/salgam.jpg"},
    {"category": "icecek", "name": "Çay", "description": "Demlik çaydanlıktan, ince belli bardakta", "price": 20, "tag": "", "image": "img/cay.jpg"},
]
_SEED_CAMPAIGNS = [
    {"label": "İKİ AL BİR HEDİYE", "title": "2 Pide Alana 1 Ayran Hediye", "description": "Herhangi 2 pide siparişine 1 yayık ayran bizden."},
    {"label": "HAFTANIN PAYLAŞIMI", "title": "2 Pide + 1 Ayran = 490₺", "description": "Payidar Karışık veya Kuşbaşılı Pide'den ikisini seç, yanına ayranı ekleyelim."},
    {"label": "ÖĞLE FIRSATI", "title": "Hafta içi 12:00-15:00 arası %15 indirim", "description": "Tüm pide ve kebaplarda geçerli, ekstra bir işlem gerekmiyor."},
    {"label": "AİLE SOFRASI", "title": "4 Kişilik Karma Menü 990₺", "description": "2 pide, 1 kebap, 2 yan ürün ve 4 ayran bir arada."},
    {"label": "NAKİT ÖDEMEDE HEDİYE", "title": "Nakit Ödemede Küçük Ayran Hediye", "description": "Siparişini kapıda nakit ödeyene küçük boy yayık ayran bizden."},
]
_SEED_TOPLINE_MESSAGES = [
    "🔥 Bugün fırından çıkanlar",
    "📍 Çünür, Isparta",
]

db.init_app(app)
with app.app_context():
    db.create_all()
    if not Product.query.first():
        for i, p in enumerate(_SEED_PRODUCTS):
            db.session.add(Product(sort_order=i, **p))
    if not Campaign.query.first():
        for i, c in enumerate(_SEED_CAMPAIGNS):
            db.session.add(Campaign(sort_order=i, **c))
    if not ToplineMessage.query.first():
        for i, t in enumerate(_SEED_TOPLINE_MESSAGES):
            db.session.add(ToplineMessage(text=t, sort_order=i))
    db.session.commit()


def get_products(active_only=True):
    query = Product.query
    if active_only:
        query = query.filter_by(is_active=True)
    return query.order_by(Product.category, Product.sort_order, Product.id).all()


@app.context_processor
def inject_topline():
    opening, closing = get_working_hours()
    if is_force_closed():
        hours_message = "🔴 Şu an kapalıyız"
    else:
        hours_message = f"🕐 {opening:%H:%M} — {closing:%H:%M} açığız"
    topline_texts = [t.text for t in ToplineMessage.query.order_by(ToplineMessage.sort_order, ToplineMessage.id).all()]
    messages = [{"text": t, "url": None} for t in topline_texts]
    messages.insert(min(1, len(messages)), {"text": hours_message, "url": None})
    messages += [
        {"text": f"🎉 {c.title}", "url": url_for("campaigns") + f"#campaign-{c.id}"}
        for c in Campaign.query.order_by(Campaign.sort_order, Campaign.id).all()
    ]
    return {"topline_messages": messages}


@app.route("/")
def home():
    featured = sorted(get_products(), key=lambda p: 0 if p.tag else 1)
    return render_template("index.html", active="home", featured_products=featured)


@app.route("/menu")
def menu():
    return render_template("menu.html", products=get_products(), active="menu")


@app.route("/kampanyalar")
def campaigns():
    all_campaigns = Campaign.query.order_by(Campaign.sort_order, Campaign.id).all()
    return render_template("campaigns.html", campaigns=all_campaigns, active="campaigns")


@app.route("/biz-kimiz")
def about():
    return render_template("about.html", active="about")


@app.route("/iletisim")
def contact():
    return render_template("contact.html", active="contact")


# ---------------------------------------------------------------------------
# Sipariş & ödeme akışı
# ---------------------------------------------------------------------------

@app.route("/siparis")
def checkout():
    opening, closing = get_working_hours()
    return render_template(
        "checkout.html",
        active="checkout",
        paytr_enabled=bool(app.config["PAYTR_MERCHANT_ID"]),
        delivery_zones=DELIVERY_ZONES,
        shop_open=is_shop_open(),
        force_closed=is_force_closed(),
        opening_str=f"{opening:%H:%M}",
        closing_str=f"{closing:%H:%M}",
    )


@app.route("/siparis/olustur", methods=["POST"])
def create_order():
    if not is_shop_open():
        opening, closing = get_working_hours()
        return jsonify(
            error=f"Şu an sipariş kabul edemiyoruz. Çalışma saatlerimiz: {opening:%H:%M}–{closing:%H:%M}."
        ), 400

    data = request.get_json(silent=True) or {}
    items = data.get("items") or []
    customer_name = (data.get("customer_name") or "").strip()
    phone = (data.get("phone") or "").strip()
    address = (data.get("address") or "").strip()
    note = (data.get("note") or "").strip()
    payment_method = data.get("payment_method")
    order_type = data.get("order_type") or "teslimat"
    neighborhood_slug = (data.get("neighborhood") or "").strip()

    if order_type not in ("teslimat", "gel_al"):
        return jsonify(error="Geçersiz sipariş türü."), 400
    if not customer_name or not phone:
        return jsonify(error="Ad soyad ve telefon zorunlu."), 400

    delivery_zone = None
    if order_type == "teslimat":
        if not address:
            return jsonify(error="Teslimat adresi zorunlu."), 400
        delivery_zone = DELIVERY_ZONES_BY_SLUG.get(neighborhood_slug)
        if not delivery_zone:
            return jsonify(error="Lütfen listeden bir mahalle seçin."), 400
    else:
        address = address or PICKUP_ADDRESS_LABEL
        neighborhood_slug = ""

    if payment_method not in ("online", "kapida"):
        return jsonify(error="Geçersiz ödeme yöntemi."), 400

    order_items = []
    total_kurus = 0
    for line in items:
        try:
            product_id = int(line.get("id"))
            quantity = int(line.get("quantity"))
        except (TypeError, ValueError, AttributeError):
            continue
        product = Product.query.filter_by(id=product_id, is_active=True).first()
        if not product or quantity <= 0:
            continue
        unit_price_kurus = product.price * 100
        order_items.append(OrderItem(
            product_id=product_id,
            product_name=product.name,
            unit_price=unit_price_kurus,
            quantity=quantity,
        ))
        total_kurus += unit_price_kurus * quantity

    if not order_items:
        return jsonify(error="Sepetiniz boş ya da geçersiz."), 400

    if delivery_zone and total_kurus < delivery_zone["min_order"] * 100:
        eksik_tl = delivery_zone["min_order"] - total_kurus / 100
        return jsonify(
            error=f"{delivery_zone['name']} için minimum sepet tutarı {delivery_zone['min_order']}₺ "
                  f"— sepetinize {eksik_tl:.0f}₺ daha ekleyin."
        ), 400

    if payment_method == "online" and not app.config["PAYTR_MERCHANT_ID"]:
        return jsonify(error="Online ödeme şu anda kullanılamıyor, kapıda ödemeyi seçin."), 503

    if payment_method == "kapida":
        window_start = datetime.utcnow() - timedelta(minutes=ORDER_RATE_LIMIT_WINDOW_MIN)
        recent_order = Order.query.filter(
            Order.phone == phone,
            Order.payment_method == "kapida",
            Order.status == "onay_bekliyor",
            Order.created_at >= window_start,
        ).first()
        if recent_order:
            return jsonify(error="Onay bekleyen bir siparişiniz zaten var, lütfen onaylanmasını bekleyin."), 429

    order = Order(
        customer_name=customer_name,
        phone=phone,
        address=address,
        note=note,
        order_type=order_type,
        neighborhood=neighborhood_slug or None,
        payment_method=payment_method,
        payment_status="pending" if payment_method == "online" else "kapida_odeme",
        status="onay_bekliyor" if payment_method == "kapida" else "alindi",
        total_price=total_kurus,
        items=order_items,
    )
    db.session.add(order)
    db.session.commit()

    if payment_method == "kapida":
        code = f"{secrets.randbelow(900000) + 100000}"
        order.confirmation_code = code
        db.session.commit()
        webhooks.send_order_confirmation_request(app.config, order, code)
        return jsonify(redirect=url_for("order_success", order_id=order.id))

    merchant_oid = f"PYD{order.id:06d}{secrets.token_hex(3)}"
    order.merchant_oid = merchant_oid
    db.session.commit()

    try:
        token = paytr.get_iframe_token(
            app.config,
            merchant_oid=merchant_oid,
            user_ip=request.remote_addr or "127.0.0.1",
            email=f"siparis{order.id}@payidarpide.local",
            amount_kurus=total_kurus,
            basket=[[item.product_name, item.unit_price / 100, item.quantity] for item in order_items],
            user_name=customer_name,
            user_address=address,
            user_phone=phone,
            ok_url=url_for("payment_ok", order_id=order.id, _external=True),
            fail_url=url_for("payment_fail", order_id=order.id, _external=True),
        )
    except paytr.PayTRError as exc:
        return jsonify(error=f"Ödeme başlatılamadı: {exc}"), 502

    return jsonify(redirect=url_for("payment_page", order_id=order.id, token=token))


@app.route("/odeme/<int:order_id>")
def payment_page(order_id):
    order = Order.query.get_or_404(order_id)
    token = request.args.get("token")
    if not token or order.payment_status != "pending":
        return redirect(url_for("order_success", order_id=order.id))
    return render_template("payment.html", order=order, token=token)


@app.route("/odeme/bildirim", methods=["POST"])
def payment_notify():
    form = request.form
    if "merchant_oid" not in form or not paytr.verify_callback(form, app.config):
        return "PAYTR notification failed: bad hash", 400

    order = Order.query.filter_by(merchant_oid=form.get("merchant_oid")).first()
    if order and order.payment_status == "pending":
        order.payment_status = "paid" if form.get("status") == "success" else "failed"
        db.session.commit()
    return "OK"


@app.route("/odeme/basarili/<int:order_id>")
def payment_ok(order_id):
    return redirect(url_for("order_success", order_id=order_id))


@app.route("/odeme/basarisiz/<int:order_id>")
def payment_fail(order_id):
    order = Order.query.get_or_404(order_id)
    return render_template("order_failed.html", order=order)


@app.route("/siparis/basarili/<int:order_id>")
def order_success(order_id):
    order = Order.query.get_or_404(order_id)
    return render_template("order_success.html", order=order)


@app.route("/webhooks/siparis-onayla", methods=["POST"])
def confirm_order_webhook():
    """Dis onay botu (ör. WhatsApp) musteriden dogru kodu aldiginda bunu cagirir."""
    expected_secret = app.config["WHATSAPP_WEBHOOK_SECRET"]
    if expected_secret and not hmac.compare_digest(request.headers.get("X-Webhook-Secret", ""), expected_secret):
        return jsonify(error="Yetkisiz."), 403

    data = request.get_json(silent=True) or {}
    order = Order.query.get(data.get("order_id"))
    code = str(data.get("code") or "")

    if not order or order.status != "onay_bekliyor":
        return jsonify(error="Onay bekleyen böyle bir sipariş yok."), 404
    if not order.confirmation_code or not hmac.compare_digest(order.confirmation_code, code):
        return jsonify(error="Kod hatalı."), 400

    order.status = "alindi"
    order.confirmed_at = datetime.utcnow()
    db.session.commit()
    return jsonify(ok=True)


# ---------------------------------------------------------------------------
# Basit yönetim paneli (sipariş takibi)
# ---------------------------------------------------------------------------

@app.route("/admin/giris", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        password = request.form.get("password", "")
        expected = app.config["ADMIN_PASSWORD"]
        if expected and hmac.compare_digest(password, expected):
            session["is_admin"] = True
            return redirect(url_for("admin_orders"))
        flash("Şifre hatalı.")
    return render_template("admin_login.html")


@app.route("/admin/cikis")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("admin_login"))


@app.route("/admin/siparisler")
def admin_orders():
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))
    orders = Order.query.order_by(Order.created_at.desc()).all()
    orders_by_status = {status: [] for status in ORDER_STATUS_COLUMNS}
    for order in orders:
        orders_by_status.setdefault(order.status, []).append(order)
    zone_names = {z["slug"]: z["name"] for z in DELIVERY_ZONES}
    return render_template(
        "admin_orders.html",
        columns=ORDER_STATUS_COLUMNS,
        orders_by_status=orders_by_status,
        total_count=len(orders),
        status_labels=ORDER_STATUS_LABELS,
        status_transitions=ORDER_STATUS_TRANSITIONS,
        zone_names=zone_names,
    )


@app.route("/admin/siparisler/<int:order_id>/durum", methods=["POST"])
def admin_update_order_status(order_id):
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))
    order = Order.query.get_or_404(order_id)
    new_status = request.form.get("durum", "")
    if new_status in ORDER_STATUS_TRANSITIONS.get(order.status, []):
        order.status = new_status
        if new_status == "alindi":
            order.confirmed_at = datetime.utcnow()
        if new_status == "iptal":
            reason = (request.form.get("sebep") or "").strip()
            order.cancel_reason = reason or "Sebep belirtilmedi"
            # Şu an bu webhook'u dinleyen bir WhatsApp botu yok — WHATSAPP_WEBHOOK_URL
            # ayarlanmamışsa sessizce atlanır, siparişi iptal etmeyi engellemez.
            webhooks.send_order_cancellation_notice(app.config, order, order.cancel_reason)
        db.session.commit()
    return redirect(url_for("admin_orders"))


@app.route("/admin/ayarlar", methods=["GET", "POST"])
def admin_settings():
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))
    if request.method == "POST":
        action = request.form.get("action")
        if action == "toggle_closed":
            set_setting("force_closed", "0" if is_force_closed() else "1")
            flash("Şu an kapalıyız olarak işaretlendi." if is_force_closed() else "Tekrar açık olarak işaretlendi.")
        else:
            opening = _parse_hhmm(request.form.get("opening_time"), None)
            closing = _parse_hhmm(request.form.get("closing_time"), None)
            if not opening or not closing:
                flash("Geçersiz saat formatı.")
            else:
                set_setting("opening_time", f"{opening:%H:%M}")
                set_setting("closing_time", f"{closing:%H:%M}")
                flash("Çalışma saatleri güncellendi.")
        return redirect(url_for("admin_settings"))

    opening, closing = get_working_hours()
    return render_template(
        "admin_settings.html",
        opening_str=f"{opening:%H:%M}",
        closing_str=f"{closing:%H:%M}",
        force_closed=is_force_closed(),
    )


@app.route("/admin/menu")
def admin_menu():
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))
    products = Product.query.order_by(Product.category, Product.sort_order, Product.id).all()
    by_category = {}
    for p in products:
        by_category.setdefault(p.category, []).append(p)
    return render_template("admin_menu.html", by_category=by_category)


@app.route("/admin/menu/ekle", methods=["POST"])
def admin_menu_add():
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))
    try:
        price = int(request.form.get("price") or 0)
    except ValueError:
        price = 0
    name = (request.form.get("name") or "").strip()
    category = (request.form.get("category") or "").strip() or "pide"
    if name and price > 0:
        db.session.add(Product(
            category=category,
            name=name,
            description=(request.form.get("description") or "").strip(),
            price=price,
            tag=(request.form.get("tag") or "").strip(),
            image=(request.form.get("image") or "").strip(),
        ))
        db.session.commit()
        flash("Ürün eklendi.")
    else:
        flash("Ürün adı ve fiyatı (0'dan büyük) zorunlu.")
    return redirect(url_for("admin_menu"))


@app.route("/admin/menu/<int:product_id>/duzenle", methods=["POST"])
def admin_menu_edit(product_id):
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))
    product = Product.query.get_or_404(product_id)
    try:
        price = int(request.form.get("price") or 0)
    except ValueError:
        price = 0
    if price > 0:
        product.category = (request.form.get("category") or product.category).strip()
        product.name = (request.form.get("name") or product.name).strip()
        product.description = (request.form.get("description") or "").strip()
        product.price = price
        product.tag = (request.form.get("tag") or "").strip()
        product.image = (request.form.get("image") or "").strip()
        product.is_active = request.form.get("is_active") == "on"
        db.session.commit()
        flash(f"{product.name} güncellendi.")
    else:
        flash("Geçersiz fiyat.")
    return redirect(url_for("admin_menu"))


@app.route("/admin/menu/<int:product_id>/sil", methods=["POST"])
def admin_menu_delete(product_id):
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))
    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()
    flash(f"{product.name} silindi.")
    return redirect(url_for("admin_menu"))


@app.route("/admin/kampanyalar", methods=["GET"])
def admin_campaigns():
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))
    all_campaigns = Campaign.query.order_by(Campaign.sort_order, Campaign.id).all()
    return render_template("admin_campaigns.html", campaigns=all_campaigns)


@app.route("/admin/kampanyalar/ekle", methods=["POST"])
def admin_campaigns_add():
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))
    title = (request.form.get("title") or "").strip()
    if title:
        db.session.add(Campaign(
            label=(request.form.get("label") or "").strip(),
            title=title,
            description=(request.form.get("description") or "").strip(),
            sort_order=int(request.form.get("sort_order") or 0),
        ))
        db.session.commit()
        flash("Kampanya eklendi.")
    else:
        flash("Kampanya başlığı zorunlu.")
    return redirect(url_for("admin_campaigns"))


@app.route("/admin/kampanyalar/<int:campaign_id>/duzenle", methods=["POST"])
def admin_campaigns_edit(campaign_id):
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))
    campaign = Campaign.query.get_or_404(campaign_id)
    title = (request.form.get("title") or "").strip()
    if title:
        campaign.label = (request.form.get("label") or "").strip()
        campaign.title = title
        campaign.description = (request.form.get("description") or "").strip()
        try:
            campaign.sort_order = int(request.form.get("sort_order") or 0)
        except ValueError:
            pass
        db.session.commit()
        flash("Kampanya güncellendi.")
    else:
        flash("Kampanya başlığı zorunlu.")
    return redirect(url_for("admin_campaigns"))


@app.route("/admin/kampanyalar/<int:campaign_id>/sil", methods=["POST"])
def admin_campaigns_delete(campaign_id):
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))
    campaign = Campaign.query.get_or_404(campaign_id)
    db.session.delete(campaign)
    db.session.commit()
    flash("Kampanya silindi.")
    return redirect(url_for("admin_campaigns"))


@app.route("/admin/bant", methods=["GET"])
def admin_topline():
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))
    messages = ToplineMessage.query.order_by(ToplineMessage.sort_order, ToplineMessage.id).all()
    return render_template("admin_topline.html", messages=messages)


@app.route("/admin/bant/ekle", methods=["POST"])
def admin_topline_add():
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))
    text = (request.form.get("text") or "").strip()
    if text:
        db.session.add(ToplineMessage(text=text, sort_order=int(request.form.get("sort_order") or 0)))
        db.session.commit()
        flash("Mesaj eklendi.")
    else:
        flash("Mesaj metni zorunlu.")
    return redirect(url_for("admin_topline"))


@app.route("/admin/bant/<int:message_id>/duzenle", methods=["POST"])
def admin_topline_edit(message_id):
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))
    message = ToplineMessage.query.get_or_404(message_id)
    text = (request.form.get("text") or "").strip()
    if text:
        message.text = text
        try:
            message.sort_order = int(request.form.get("sort_order") or 0)
        except ValueError:
            pass
        db.session.commit()
        flash("Mesaj güncellendi.")
    else:
        flash("Mesaj metni zorunlu.")
    return redirect(url_for("admin_topline"))


@app.route("/admin/bant/<int:message_id>/sil", methods=["POST"])
def admin_topline_delete(message_id):
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))
    message = ToplineMessage.query.get_or_404(message_id)
    db.session.delete(message)
    db.session.commit()
    flash("Mesaj silindi.")
    return redirect(url_for("admin_topline"))


if __name__ == "__main__":
    app.run(debug=True)
