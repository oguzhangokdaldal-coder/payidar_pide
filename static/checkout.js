function isDelivery() {
  const el = document.querySelector('input[name="order_type"]:checked');
  return !el || el.value === 'teslimat';
}

function getSelectedZone() {
  const select = document.querySelector('#neighborhoodSelect');
  const opt = select?.selectedOptions[0];
  if (!opt) return null;
  return { value: opt.value, min: Number(opt.dataset.min), lat: Number(opt.dataset.lat), lng: Number(opt.dataset.lng) };
}

function cartTotal() {
  return cart.reduce((sum, item) => sum + item.price * item.quantity, 0);
}

const checkoutForm = document.querySelector('#checkoutForm');
const shopOpen = checkoutForm ? checkoutForm.dataset.shopOpen === 'true' : true;

function renderCheckoutSummary() {
  const container = document.querySelector('#orderSummary');
  const submitBtn = document.querySelector('#submitOrder');
  const minNote = document.querySelector('#minOrderNote');
  if (!container) return;

  if (!shopOpen) {
    if (submitBtn) submitBtn.disabled = true;
    // Buton zaten sunucu tarafında devre dışı/"Şu an kapalıyız" olarak render edildi,
    // dükkan kapalıyken sepet/mahalle değişse de tekrar etkinleştirmiyoruz.
  }

  if (!cart.length) {
    container.innerHTML = '<h3>Sepetin</h3><p class="summary-empty">Sepetin boş. <a href="/menu">Menüye dön →</a></p>';
    if (submitBtn && shopOpen) submitBtn.disabled = true;
    return;
  }

  const lines = cart.map(item => `
    <div class="summary-line">
      <div>${item.name}<small>${item.quantity} adet</small></div>
      <strong>${formatPrice(item.price * item.quantity)}</strong>
    </div>`).join('');
  const total = cartTotal();
  container.innerHTML = `<h3>Sepetin</h3>${lines}<div class="summary-total"><span>Toplam</span><span>${formatPrice(total)}</span></div>`;

  if (isDelivery()) {
    const zone = getSelectedZone();
    if (zone && minNote) {
      if (total < zone.min) {
        minNote.textContent = `Bu mahalle için minimum sepet tutarı ${formatPrice(zone.min)} — sepetine ${formatPrice(zone.min - total)} daha ekle.`;
        minNote.classList.add('min-not-met');
      } else {
        minNote.textContent = `Minimum sepet tutarı: ${formatPrice(zone.min)} ✓`;
        minNote.classList.remove('min-not-met');
      }
    }
  } else if (minNote) {
    minNote.textContent = '';
    minNote.classList.remove('min-not-met');
  }

  // Not: minimum tutara ulaşılmadığında butonu kilitlemiyoruz — müşteri
  // "Siparişi onayla"ya bastığında alttaki net uyarıyı görsün istiyoruz
  // (submit dinleyicisine bakın), sessizce devre dışı bir buton yerine.
  if (submitBtn && shopOpen) submitBtn.disabled = false;
}
document.addEventListener('cart:updated', renderCheckoutSummary);

function updateOrderTypeUI() {
  const deliveryFields = document.querySelector('#deliveryFields');
  const addressField = document.querySelector('#addressField');
  if (!deliveryFields) return;
  const delivery = isDelivery();
  deliveryFields.hidden = !delivery;
  if (addressField) addressField.required = delivery;
  renderCheckoutSummary();
}
document.querySelectorAll('input[name="order_type"]').forEach(radio => radio.addEventListener('change', updateOrderTypeUI));
document.querySelector('#neighborhoodSelect')?.addEventListener('change', renderCheckoutSummary);

function haversineKm(lat1, lng1, lat2, lng2) {
  const R = 6371;
  const toRad = deg => deg * Math.PI / 180;
  const dLat = toRad(lat2 - lat1);
  const dLng = toRad(lng2 - lng1);
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

const useLocationBtn = document.querySelector('#useLocationBtn');
if (useLocationBtn) {
  const defaultLabel = useLocationBtn.textContent;
  useLocationBtn.addEventListener('click', () => {
    const select = document.querySelector('#neighborhoodSelect');
    if (!navigator.geolocation || !select) {
      alert('Tarayıcın konum özelliğini desteklemiyor, mahalleni listeden elle seçebilirsin.');
      return;
    }
    useLocationBtn.disabled = true;
    useLocationBtn.textContent = 'Konum alınıyor…';
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const { latitude, longitude } = pos.coords;
        let nearest = null;
        let nearestDist = Infinity;
        Array.from(select.options).forEach(opt => {
          const d = haversineKm(latitude, longitude, Number(opt.dataset.lat), Number(opt.dataset.lng));
          if (d < nearestDist) { nearestDist = d; nearest = opt; }
        });
        if (nearest) {
          select.value = nearest.value;
          renderCheckoutSummary();
        }
        useLocationBtn.disabled = false;
        useLocationBtn.textContent = defaultLabel;
      },
      () => {
        useLocationBtn.disabled = false;
        useLocationBtn.textContent = defaultLabel;
        alert('Konum alınamadı (izin verilmedi ya da bulunamadı) — mahalleni listeden elle seçebilirsin.');
      },
      { timeout: 8000 }
    );
  });
}

if (checkoutForm) {
  renderCheckoutSummary();

  checkoutForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const errorEl = document.querySelector('#formError');
    const submitBtn = document.querySelector('#submitOrder');
    errorEl.hidden = true;

    if (!shopOpen) {
      errorEl.textContent = 'Şu an kapalıyız, sipariş alamıyoruz.';
      errorEl.hidden = false;
      return;
    }

    if (!cart.length) {
      errorEl.textContent = 'Sepetin boş, önce menüden ürün ekle.';
      errorEl.hidden = false;
      return;
    }

    const delivery = isDelivery();
    const zone = delivery ? getSelectedZone() : null;
    if (delivery && zone && cartTotal() < zone.min) {
      errorEl.textContent = `Bu mahalle için minimum sepet tutarı ${formatPrice(zone.min)} — sepetine ${formatPrice(zone.min - cartTotal())} daha ekle.`;
      errorEl.hidden = false;
      return;
    }

    const formData = new FormData(checkoutForm);
    const payload = {
      customer_name: formData.get('customer_name'),
      phone: formData.get('phone'),
      address: delivery ? formData.get('address') : '',
      note: formData.get('note'),
      payment_method: formData.get('payment_method'),
      order_type: delivery ? 'teslimat' : 'gel_al',
      neighborhood: delivery ? formData.get('neighborhood') : '',
      items: cart.map(item => ({ id: item.id, quantity: item.quantity })),
    };

    submitBtn.disabled = true;
    try {
      const response = await fetch('/siparis/olustur', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) {
        errorEl.textContent = data.error || 'Bir hata oluştu, tekrar dene.';
        errorEl.hidden = false;
        submitBtn.disabled = false;
        return;
      }
      window.location.href = data.redirect;
    } catch (err) {
      errorEl.textContent = 'Bağlantı hatası, tekrar dene.';
      errorEl.hidden = false;
      submitBtn.disabled = false;
    }
  });
}
