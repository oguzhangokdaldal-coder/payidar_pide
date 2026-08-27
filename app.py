import hmac
import os
import secrets
from datetime import datetime, timedelta

from dotenv import load_dotenv
from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for

import paytr
import webhooks
from models import Order, OrderItem, db

load_dotenv()

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

db.init_app(app)
with app.app_context():
    db.create_all()

PRODUCTS = [
    {"id": 1, "category": "pide", "name": "Özel Karışık Pide", "description": "Kuşbaşı, kaşar, sucuk ve közlenmiş biber", "price": 250, "tag": "Favori", "image": "img/karısik_pizza.jpg"},
    {"id": 2, "category": "pide", "name": "Kuşbaşılı Kaşarlı Pide", "description": "Zırh kıyması, bol kaşar ve tereyağı", "price": 200, "tag": "Yeni", "image": "img/kusbasi_kasar.jpg"},
    {"id": 3, "category": "pide", "name": "Kıymalı Pide", "description": "İnce kıyma, domates, biber ve maydanoz", "price": 150, "tag": "", "image": "img/kiymali.jpg"},
    {"id": 4, "category": "pide", "name": "Kaşarlı Pide", "description": "Uzayan kaşar, tereyağı ve çıtır hamur", "price": 160, "tag": "", "image": "img/kasarlipide.jpg"},
    {"id": 5, "category": "pide", "name": "Sucuklu Kaşarlı Pide", "description": "Baharatlı sucuk ve bol kaşar", "price": 250, "tag": "", "image": "img/sucuklu_kasar.jpg"},
    {"id": 6, "category": "pide", "name": "Lahmacun", "description": "İnce açılmış hamur, bol malzeme, taş fırında", "price": 140, "tag": "", "image": "img/lahmacun.jpg"},
    {"id": 7, "category": "pide", "name": "Peynirli Pide", "description": "Bol beyaz peynir ve maydanoz", "price": 150, "tag": "", "image": ""},
    {"id": 8, "category": "pide", "name": "Kıymalı Kaşarlı Pide", "description": "İnce kıyma ve bol kaşar bir arada", "price": 170, "tag": "", "image": ""},
    {"id": 9, "category": "pide", "name": "Kuşbaşılı Pide", "description": "Zırh kuşbaşı, domates ve biber", "price": 180, "tag": "", "image": ""},
    {"id": 10, "category": "pide", "name": "Sade Kıymalı Pide", "description": "Bol kıyma, sade ve doyurucu", "price": 250, "tag": "", "image": ""},

    {"id": 11, "category": "izgara", "name": "Şiş Köfte", "description": "Izgara ateşinde közlenmiş şiş köfte", "price": 300, "tag": "", "image": ""},
    {"id": 12, "category": "izgara", "name": "Adana Kebap", "description": "Zırhta çekilmiş acılı et, köz sebzeler ve lavaş", "price": 300, "tag": "", "image": "img/adana_veya_urfa.jpg"},
    {"id": 13, "category": "izgara", "name": "Izgara Köfte", "description": "El yapımı ızgara köfte", "price": 300, "tag": "", "image": ""},
    {"id": 14, "category": "izgara", "name": "Tavuk Şiş", "description": "Marine edilmiş tavuk şiş", "price": 300, "tag": "", "image": ""},

    {"id": 15, "category": "durum", "name": "Adana Dürüm", "description": "Adana kebap, lavaş içinde sarılır", "price": 300, "tag": "", "image": ""},
    {"id": 16, "category": "durum", "name": "Tavuk Dürüm", "description": "Marine tavuk şiş, lavaş içinde sarılır", "price": 300, "tag": "", "image": ""},
    {"id": 17, "category": "durum", "name": "Şiş Köfte Dürüm", "description": "Şiş köfte, lavaş içinde sarılır", "price": 300, "tag": "", "image": ""},

    {"id": 18, "category": "icecek", "name": "Yayık Ayran", "description": "Günlük yoğurttan, buz gibi", "price": 45, "tag": "", "image": ""},
    {"id": 19, "category": "icecek", "name": "Kutu Kola", "description": "330 ml, buz gibi", "price": 40, "tag": "", "image": ""},
    {"id": 20, "category": "icecek", "name": "Fanta", "description": "330 ml, buz gibi", "price": 40, "tag": "", "image": ""},
    {"id": 21, "category": "icecek", "name": "Sprite", "description": "330 ml, buz gibi", "price": 40, "tag": "", "image": ""},
    {"id": 22, "category": "icecek", "name": "Soda", "description": "200 ml, sade", "price": 25, "tag": "", "image": ""},
    {"id": 23, "category": "icecek", "name": "Şalgam Suyu", "description": "Acılı, geleneksel usul", "price": 35, "tag": "", "image": ""},
    {"id": 24, "category": "icecek", "name": "Çay", "description": "Demlik çaydanlıktan, ince belli bardakta", "price": 20, "tag": "", "image": ""},
]
PRODUCTS_BY_ID = {item["id"]: item for item in PRODUCTS}

CAMPAIGNS = [
    {"label": "İKİ AL BİR HEDİYE", "title": "2 Pide Alana 1 Ayran Hediye", "description": "Herhangi 2 pide siparişine 1 yayık ayran bizden."},
    {"label": "HAFTANIN PAYLAŞIMI", "title": "2 Pide + 1 Ayran = 490₺", "description": "Payidar Karışık veya Kuşbaşılı Pide'den ikisini seç, yanına ayranı ekleyelim."},
    {"label": "ÖĞLE FIRSATI", "title": "Hafta içi 12:00-15:00 arası %15 indirim", "description": "Tüm pide ve kebaplarda geçerli, ekstra bir işlem gerekmiyor."},
    {"label": "AİLE SOFRASI", "title": "4 Kişilik Karma Menü 990₺", "description": "2 pide, 1 kebap, 2 yan ürün ve 4 ayran bir arada."},
]

TOPLINE_MESSAGES = [
    "🔥 Bugün fırından çıkanlar",
    "🕐 10:00 — 22:00 açığız",
    "📍 Çünür, Isparta",
] + [f"🎉 {c['title']}" for c in CAMPAIGNS]


@app.context_processor
def inject_topline():
    return {"topline_messages": TOPLINE_MESSAGES}


@app.route("/")
def home():
    featured = sorted(PRODUCTS, key=lambda p: 0 if p["tag"] else 1)
    return render_template("index.html", active="home", featured_products=featured)


@app.route("/menu")
def menu():
    return render_template("menu.html", products=PRODUCTS, active="menu")


@app.route("/kampanyalar")
def campaigns():
    return render_template("campaigns.html", campaigns=CAMPAIGNS, active="campaigns")


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
    return render_template("checkout.html", active="checkout", paytr_enabled=bool(app.config["PAYTR_MERCHANT_ID"]))


@app.route("/siparis/olustur", methods=["POST"])
def create_order():
    data = request.get_json(silent=True) or {}
    items = data.get("items") or []
    customer_name = (data.get("customer_name") or "").strip()
    phone = (data.get("phone") or "").strip()
    address = (data.get("address") or "").strip()
    note = (data.get("note") or "").strip()
    payment_method = data.get("payment_method")

    if not customer_name or not phone or not address:
        return jsonify(error="Ad soyad, telefon ve adres zorunlu."), 400
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
        product = PRODUCTS_BY_ID.get(product_id)
        if not product or quantity <= 0:
            continue
        unit_price_kurus = product["price"] * 100
        order_items.append(OrderItem(
            product_id=product_id,
            product_name=product["name"],
            unit_price=unit_price_kurus,
            quantity=quantity,
        ))
        total_kurus += unit_price_kurus * quantity

    if not order_items:
        return jsonify(error="Sepetiniz boş ya da geçersiz."), 400

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
    return render_template("admin_orders.html", orders=orders)


@app.route("/admin/siparisler/<int:order_id>/onayla", methods=["POST"])
def admin_confirm_order(order_id):
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))
    order = Order.query.get_or_404(order_id)
    if order.status == "onay_bekliyor":
        order.status = "alindi"
        order.confirmed_at = datetime.utcnow()
        db.session.commit()
    return redirect(url_for("admin_orders"))


if __name__ == "__main__":
    app.run(debug=True)
