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
      ? cart.map(item => `<div class="cart-line"><img src="${item.image}" alt=""><div><h4>${item.name}</h4><small>${item.quantity} adet</small></div><strong>${formatPrice(item.price * item.quantity)}</strong></div>`).join('')
      : `<div class="empty-cart"><span>⌁</span><h3>Sepetin henüz boş</h3><p>Fırından çıkan bir şeyler eklemeye ne dersin?</p><a href="/menu" id="startShopping">Menüye git →</a></div>`;
    document.querySelector('#startShopping')?.addEventListener('click', closeCart);
  }
  saveCart();
}

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

document.querySelector('#openCart')?.addEventListener('click', openCart);
document.querySelector('#closeCart')?.addEventListener('click', closeCart);
document.querySelector('#cartOverlay')?.addEventListener('click', closeCart);

updateCart();
