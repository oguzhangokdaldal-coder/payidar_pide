import json
import urllib.request


def send_order_confirmation_request(config, order, code):
    """Siparis onay kodunu dogrulayacak dis bota (ör. WhatsApp botu) webhook gonderir.

    WHATSAPP_WEBHOOK_URL ayarlanmamissa sessizce atlanir (bot henuz baglanmadi demektir).
    Bu cagri siparis olusturmayi asla engellemez; hata olursa loglanip gecilir.
    """
    url = config.get("WHATSAPP_WEBHOOK_URL")
    if not url:
        return False

    payload = {
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
    }
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
