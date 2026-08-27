import base64
import hashlib
import hmac
import json
import urllib.parse
import urllib.request

PAYTR_TOKEN_URL = "https://www.paytr.com/odeme/api/get-token"


class PayTRError(Exception):
    pass


def _hmac_b64(message: str, merchant_key: str) -> str:
    digest = hmac.new(merchant_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def get_iframe_token(config, *, merchant_oid, user_ip, email, amount_kurus,
                      basket, user_name, user_address, user_phone,
                      ok_url, fail_url):
    """PayTR iFrame API'ye istek atar, iframe icin gecici token doner."""
    user_basket = base64.b64encode(
        json.dumps(basket, ensure_ascii=False).encode("utf-8")
    ).decode("utf-8")

    test_mode = "1" if config["PAYTR_TEST_MODE"] else "0"
    no_installment = "0"
    max_installment = "0"
    currency = "TL"

    hash_str = (
        config["PAYTR_MERCHANT_ID"] + user_ip + merchant_oid + email
        + str(amount_kurus) + user_basket + no_installment + max_installment
        + currency + test_mode
    )
    token = _hmac_b64(hash_str + config["PAYTR_MERCHANT_SALT"], config["PAYTR_MERCHANT_KEY"])

    form = {
        "merchant_id": config["PAYTR_MERCHANT_ID"],
        "user_ip": user_ip,
        "merchant_oid": merchant_oid,
        "email": email,
        "payment_amount": amount_kurus,
        "paytr_token": token,
        "user_basket": user_basket,
        "debug_on": "1" if config["PAYTR_TEST_MODE"] else "0",
        "no_installment": no_installment,
        "max_installment": max_installment,
        "user_name": user_name,
        "user_address": user_address,
        "user_phone": user_phone,
        "merchant_ok_url": ok_url,
        "merchant_fail_url": fail_url,
        "timeout_limit": "30",
        "currency": currency,
        "test_mode": test_mode,
    }

    data = urllib.parse.urlencode(form).encode("utf-8")
    request = urllib.request.Request(PAYTR_TOKEN_URL, data=data)
    with urllib.request.urlopen(request, timeout=15) as response:
        result = json.loads(response.read().decode("utf-8"))

    if result.get("status") != "success":
        raise PayTRError(result.get("reason", "PayTR token alinamadi"))
    return result["token"]


def verify_callback(form, config):
    """PayTR bildirim (webhook) POST'unun hash'ini dogrular."""
    hash_str = form["merchant_oid"] + config["PAYTR_MERCHANT_SALT"] + form["status"] + form["total_amount"]
    expected = _hmac_b64(hash_str, config["PAYTR_MERCHANT_KEY"])
    return hmac.compare_digest(expected, form.get("hash", ""))
