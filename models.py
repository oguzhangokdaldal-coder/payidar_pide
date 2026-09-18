from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

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


class Setting(db.Model):
    """Yönetim panelinden değiştirilebilen basit anahtar/değer ayarları
    (örn. çalışma saatleri). .env'deki değerler yalnızca ilk/varsayılan
    değer olarak kullanılır, buradaki kayıt varsa onu geçersiz kılar."""
    __tablename__ = "settings"

    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.String(200), nullable=False)
