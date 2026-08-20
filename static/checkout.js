function renderCheckoutSummary() {
  const container = document.querySelector('#orderSummary');
  const submitBtn = document.querySelector('#submitOrder');
  if (!container) return;

  if (!cart.length) {
    container.innerHTML = '<h3>Sepetin</h3><p class="summary-empty">Sepetin boş. <a href="/menu">Menüye dön →</a></p>';
    if (submitBtn) submitBtn.disabled = true;
    return;
  }

  const lines = cart.map(item => `
    <div class="summary-line">
      <div>${item.name}<small>${item.quantity} adet</small></div>
      <strong>${formatPrice(item.price * item.quantity)}</strong>
    </div>`).join('');
  const total = cart.reduce((sum, item) => sum + item.price * item.quantity, 0);
  container.innerHTML = `<h3>Sepetin</h3>${lines}<div class="summary-total"><span>Toplam</span><span>${formatPrice(total)}</span></div>`;
  if (submitBtn) submitBtn.disabled = false;
}

const checkoutForm = document.querySelector('#checkoutForm');
if (checkoutForm) {
  renderCheckoutSummary();

  checkoutForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const errorEl = document.querySelector('#formError');
    const submitBtn = document.querySelector('#submitOrder');
    errorEl.hidden = true;

    if (!cart.length) {
      errorEl.textContent = 'Sepetin boş, önce menüden ürün ekle.';
      errorEl.hidden = false;
      return;
    }

    const formData = new FormData(checkoutForm);
    const payload = {
      customer_name: formData.get('customer_name'),
      phone: formData.get('phone'),
      address: formData.get('address'),
      note: formData.get('note'),
      payment_method: formData.get('payment_method'),
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
