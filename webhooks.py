import json
import urllib.request


def _post_webhook(config, payload):
    """Ortak webhook gonderme mantigi.

    WHATSAPP_WEBHOOK_URL ayarlanmamissa sessizce atlanir (bot henuz baglanmadi
    demektir — orn. henuz Baileys tabanli bir WhatsApp botu kurulmadi). Bu
    cagri hicbir zaman ana islemi (siparis olusturma/iptal vb.) engellemez;
    hata olursa sessizce gecilir.
    """
    url = config.get("WHATSAPP_WEBHOOK_URL")
    if not url:
        return False

    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    secret = config.get("WHATSAPP_WEBHOOK_SECRET")
    if secret:
        headers["X-Webhook-Secret"] = secret

    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=5):
            pass
        return True
    except Exception:
        return False


def send_order_confirmation_request(config, order, code):
    """Siparis onay kodunu dogrulayacak dis bota webhook gonderir."""
    return _post_webhook(config, {
        "event": "order.confirmation_requested",
        "order_id": order.id,
        "phone": order.phone,
        "customer_name": order.customer_name,
        "code": code,
        "total_tl": order.total_price_tl,
        "items": [
            {"name": item.product_name, "quantity": item.quantity}
            for item in order.items
        ],
    })


def send_order_cancellation_notice(config, order, reason):
    """Siparis iptal edildiginde musteriye haber verecek dis bota webhook gonderir.

    Su an bu webhook'u dinleyen bir bot yok (WhatsApp botu ileride kurulacak,
    ornegin Baileys ile) — WHATSAPP_WEBHOOK_URL ayarlaninca otomatik devreye
    girer, kod tarafinda ek bir degisiklik gerekmez.
    """
    return _post_webhook(config, {
        "event": "order.cancelled",
        "order_id": order.id,
        "phone": order.phone,
        "customer_name": order.customer_name,
        "reason": reason or "",
        "total_tl": order.total_price_tl,
    })
