import hmac
import os
import secrets

from dotenv import load_dotenv
from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for

import paytr
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

db.init_app(app)
with app.app_context():
    db.create_all()

PRODUCTS = [
    {"id": 1, "category": "pide", "name": "Payidar Karışık", "description": "Kuşbaşı, kaşar, sucuk ve közlenmiş biber", "price": 290, "tag": "Favori", "image": "img/karısik_pizza.jpg"},
    {"id": 2, "category": "pide", "name": "Kuşbaşı Kaşarlı Pide", "description": "Zırh kıyması, bol kaşar ve tereyağı", "price": 260, "tag": "Yeni", "image": "img/kusbasi_kasar.jpg"},
    {"id": 3, "category": "pide", "name": "Kıymalı Pide", "description": "İnce kıyma, domates, biber ve maydanoz", "price": 230, "tag": "", "image": "img/kiymali.jpg"},
    {"id": 4, "category": "pide", "name": "Kaşarlı Pide", "description": "Uzayan kaşar, tereyağı ve çıtır hamur", "price": 210, "tag": "", "image": "img/kasarlipide.jpg"},
    {"id": 5, "category": "pide", "name": "Sucuklu Kaşarlı Pide", "description": "Baharatlı sucuk ve bol kaşar", "price": 250, "tag": "", "image": "img/sucuklu_kasar.jpg"},
    {"id": 6, "category": "pide", "name": "Lahmacun", "description": "İnce açılmış hamur, bol malzeme, taş fırında", "price": 90, "tag": "", "image": "img/lahmacun.jpg"},
    {"id": 7, "category": "kebap", "name": "Adana veya Urfa Kebap", "description": "Zırhta çekilmiş et, köz sebzeler ve lavaş", "price": 310, "tag": "", "image": "img/adana_veya_urfa.jpg"},
    {"id": 8, "category": "yan", "name": "Fırın Sütlaç", "description": "Geleneksel tarif, çıtır fındık dokunuşuyla", "price": 95, "tag": "Tatlı", "image": ""},
    {"id": 9, "category": "yan", "name": "Közlenmiş Biber", "description": "Taş fırında közlenmiş, zeytinyağlı", "price": 80, "tag": "", "image": ""},
    {"id": 10, "category": "yan", "name": "Yayık Ayran", "description": "Günlük yoğurttan, buz gibi", "price": 45, "tag": "", "image": ""},
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
    "🕐 12:00 — 23:30 açığız",
    "📍 Merkez, İstanbul",
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

    order = Order(
        customer_name=customer_name,
        phone=phone,
        address=address,
        note=note,
        payment_method=payment_method,
        payment_status="pending" if payment_method == "online" else "kapida_odeme",
        total_price=total_kurus,
        items=order_items,
    )
    db.session.add(order)
    db.session.commit()

    if payment_method == "kapida":
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


if __name__ == "__main__":
    app.run(debug=True)
