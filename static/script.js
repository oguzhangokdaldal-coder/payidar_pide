const CART_KEY = 'payidar_cart';
const formatPrice = value => `${value.toLocaleString('tr-TR')}₺`;

let cart = [];
try { cart = JSON.parse(localStorage.getItem(CART_KEY)) || []; } catch (e) { cart = []; }

function saveCart() {
  localStorage.setItem(CART_KEY, JSON.stringify(cart));
}

function addToCart(id, data) {
  const existing = cart.find(line => line.id === id);
  if (existing) existing.quantity += 1;
  else cart.push({ id, name: data.name, price: Number(data.price), image: data.image, quantity: 1 });
  updateCart();
  const toast = document.querySelector('#toast');
  if (!toast) return;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 1800);
}

function changeQuantity(id, delta) {
  const line = cart.find(item => item.id === id);
  if (!line) return;
  line.quantity += delta;
  if (line.quantity <= 0) cart = cart.filter(item => item.id !== id);
  updateCart();
}

function removeFromCart(id) {
  cart = cart.filter(item => item.id !== id);
  updateCart();
}

function updateCart() {
  const count = cart.reduce((total, item) => total + item.quantity, 0);
  const total = cart.reduce((sum, item) => sum + item.price * item.quantity, 0);
  const cartCount = document.querySelector('#cartCount');
  const drawerCount = document.querySelector('#drawerCount');
  const cartTotal = document.querySelector('#cartTotal');
  if (cartCount) cartCount.textContent = count;
  if (drawerCount) drawerCount.textContent = count;
  if (cartTotal) cartTotal.textContent = formatPrice(total);
  const container = document.querySelector('#cartItems');
  if (container) {
    container.innerHTML = cart.length
      ? cart.map(item => `
        <div class="cart-line">
          ${item.image ? `<img src="${item.image}" alt="">` : '<span class="cart-line-noimage">🍽️</span>'}
          <div class="cart-line-info">
            <h4>${item.name}</h4>
            <div class="qty-control">
              <button type="button" class="qty-btn" data-action="decrease" data-id="${item.id}" aria-label="Azalt">−</button>
              <span>${item.quantity}</span>
              <button type="button" class="qty-btn" data-action="increase" data-id="${item.id}" aria-label="Artır">+</button>
            </div>
          </div>
          <div class="cart-line-right">
            <strong>${formatPrice(item.price * item.quantity)}</strong>
            <button type="button" class="cart-remove" data-action="remove" data-id="${item.id}" aria-label="${item.name} ürününü sepetten çıkar">Kaldır</button>
          </div>
        </div>`).join('')
      : `<div class="empty-cart"><span>⌁</span><h3>Sepetin henüz boş</h3><p>Fırından çıkan bir şeyler eklemeye ne dersin?</p><a href="/menu" id="startShopping">Menüye git →</a></div>`;
    document.querySelector('#startShopping')?.addEventListener('click', closeCart);
  }
  saveCart();
}

document.querySelector('#cartItems')?.addEventListener('click', (event) => {
  const button = event.target.closest('.qty-btn, .cart-remove');
  if (!button) return;
  const id = Number(button.dataset.id);
  if (button.dataset.action === 'increase') changeQuantity(id, 1);
  else if (button.dataset.action === 'decrease') changeQuantity(id, -1);
  else if (button.dataset.action === 'remove') removeFromCart(id);
});

function openCart() {
  document.querySelector('#cartDrawer')?.classList.add('open');
  document.querySelector('#cartOverlay')?.classList.add('open');
  document.body.style.overflow = 'hidden';
}
function closeCart() {
  document.querySelector('#cartDrawer')?.classList.remove('open');
  document.querySelector('#cartOverlay')?.classList.remove('open');
  document.body.style.overflow = '';
}

document.querySelectorAll('.add-button').forEach(button => {
  button.addEventListener('click', () => addToCart(Number(button.dataset.id), button.dataset));
});

const categoryTabs = document.querySelectorAll('.category-tabs button');
if (categoryTabs.length) {
  categoryTabs.forEach(button => {
    button.addEventListener('click', () => {
      document.querySelector('.category-tabs .active')?.classList.remove('active');
      button.classList.add('active');
      const filter = button.dataset.filter;
      document.querySelectorAll('.product-card').forEach(card => {
        card.style.display = (filter === 'all' || card.dataset.category === filter) ? '' : 'none';
      });
    });
  });
}

const menuToggle = document.querySelector('#menuToggle');
const siteNav = document.querySelector('#siteNav');
if (menuToggle && siteNav) {
  menuToggle.addEventListener('click', () => {
    const isOpen = siteNav.classList.toggle('open');
    menuToggle.classList.toggle('open', isOpen);
    menuToggle.setAttribute('aria-expanded', String(isOpen));
  });
  siteNav.querySelectorAll('a').forEach(link => {
    link.addEventListener('click', () => {
      siteNav.classList.remove('open');
      menuToggle.classList.remove('open');
      menuToggle.setAttribute('aria-expanded', 'false');
    });
  });
}

document.querySelector('#openCart')?.addEventListener('click', openCart);
document.querySelector('#closeCart')?.addEventListener('click', closeCart);
document.querySelector('#cartOverlay')?.addEventListener('click', closeCart);
document.querySelector('.checkout-button')?.addEventListener('click', () => {
  if (cart.length) window.location.href = '/siparis';
});

updateCart();
