from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=True)  # misafir siparişte boş
    customer_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    address = db.Column(db.String(400), nullable=False)
    note = db.Column(db.String(300), default="")

    order_type = db.Column(db.String(20), default="teslimat")  # teslimat | gel_al
    neighborhood = db.Column(db.String(50), nullable=True)  # yalnızca teslimat siparişlerinde dolu

    payment_method = db.Column(db.String(20), nullable=False)  # "online" | "kapida"
    payment_status = db.Column(db.String(20), default="pending")  # pending | paid | failed
    status = db.Column(db.String(20), default="alindi")  # onay_bekliyor | alindi | hazirlaniyor | yolda | teslim_edildi

    confirmation_code = db.Column(db.String(10), nullable=True)
    confirmed_at = db.Column(db.DateTime, nullable=True)
    cancel_reason = db.Column(db.String(300), nullable=True)  # yalnızca iptal edilen siparişlerde dolu

    total_price = db.Column(db.Integer, nullable=False)  # kuruş cinsinden (PayTR ile uyumlu)
    merchant_oid = db.Column(db.String(64), unique=True, nullable=True)

    items = db.relationship("OrderItem", backref="order", cascade="all, delete-orphan")

    @property
    def total_price_tl(self):
        return self.total_price / 100


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)

    product_id = db.Column(db.Integer, nullable=False)
    product_name = db.Column(db.String(120), nullable=False)
    unit_price = db.Column(db.Integer, nullable=False)  # kuruş
    quantity = db.Column(db.Integer, nullable=False)

    @property
    def line_total_tl(self):
        return (self.unit_price * self.quantity) / 100


class Customer(db.Model):
    """Müşteri hesabı (giriş opsiyonel — misafir siparişi hâlâ mümkün).
    Giriş yapan müşterinin e-postası alınmış olur, bilgileri sipariş
    formuna otomatik dolar, geçmiş siparişlerini /hesabim'den görebilir."""
    __tablename__ = "customers"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), default="")
    address = db.Column(db.String(400), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    orders = db.relationship("Order", backref="customer")


class Setting(db.Model):
    """Yönetim panelinden değiştirilebilen basit anahtar/değer ayarları
    (örn. çalışma saatleri, elle kapalı anahtarı). .env'deki değerler
    yalnızca ilk/varsayılan değer olarak kullanılır, buradaki kayıt varsa
    onu geçersiz kılar."""
    __tablename__ = "settings"

    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.String(200), nullable=False)


class Product(db.Model):
    """Menü ürünü. Eskiden app.py içinde sabit kodlu bir liste olan PRODUCTS'ın
    yerini alır — yönetim panelinden (/admin/menu) düzenlenebilir."""
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(30), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(300), default="")
    price = db.Column(db.Integer, nullable=False)  # ₺ (tam sayı)
    tag = db.Column(db.String(30), default="")
    image = db.Column(db.String(200), default="")
    is_active = db.Column(db.Boolean, default=True)  # false: menüde gizli (tükendi vb.)
    sort_order = db.Column(db.Integer, default=0)


class Campaign(db.Model):
    """Kampanya. Eskiden app.py içinde sabit kodlu CAMPAIGNS listesinin
    yerini alır — yönetim panelinden (/admin/kampanyalar) düzenlenebilir."""
    __tablename__ = "campaigns"

    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(60), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.String(300), default="")
    sort_order = db.Column(db.Integer, default=0)

    start_at = db.Column(db.DateTime, nullable=True)  # boş: başlangıç sınırı yok
    end_at = db.Column(db.DateTime, nullable=True)  # boş: bitiş sınırı yok
    rule_type = db.Column(db.String(30), default="")  # "": kural yok, sadece bilgilendirme kartı
    rule_params = db.Column(db.Text, default="")  # rule_type'a göre değişen JSON


class ToplineMessage(db.Model):
    """Üstte kayan bandın sabit (kampanya olmayan) mesajları — örn. çalışma
    saatleri dışındaki genel duyurular. Yönetim panelinden (/admin/bant)
    düzenlenebilir."""
    __tablename__ = "topline_messages"

    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(150), nullable=False)
    sort_order = db.Column(db.Integer, default=0)
