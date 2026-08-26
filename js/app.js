const FALLBACK_PRODUCTS = [
  { id: "pao-frances", name: "Pão Francês", cat: "Pães", price: 0.9, unit: "un", img: "img/pao-frances.jpg", desc: "Crocante por fora, macio por dentro. Forno de madrugada." },
  { id: "pao-caseiro", name: "Pão Caseiro", cat: "Pães", price: 18.9, unit: "un", img: "img/pao-caseiro.jpg", desc: "Fermentação lenta, casca rústica e miolo alveolado." },
  { id: "croissant", name: "Croissant Manteiga", cat: "Pães", price: 9.9, unit: "un", img: "img/croissant.jpg", desc: "Massa folhada com manteiga extra, camadas crocantes." },
  { id: "bolo-fuba", name: "Bolo de Fubá", cat: "Bolos", price: 12.0, unit: "fatia", img: "img/bolo-fuba.jpg", desc: "Receita da casa, fubá cremoso e cobertura dourada." },
  { id: "bolo-choco", name: "Bolo de Chocolate", cat: "Bolos", price: 14.0, unit: "fatia", img: "img/doces.jpg", desc: "Duas camadas, ganache intensa e textura úmida." },
  { id: "brigadeiro", name: "Brigadeiro Gourmet", cat: "Doces", price: 4.5, unit: "un", img: "img/doces.jpg", desc: "Chocolate 50% e granulado belga." },
  { id: "sonho", name: "Sonho de Padaria", cat: "Doces", price: 7.9, unit: "un", img: "img/doces.jpg", desc: "Frito na hora, açúcar e recheio de creme." },
  { id: "pao-queijo", name: "Pão de Queijo", cat: "Salgados", price: 3.5, unit: "un", img: "img/salgados.jpg", desc: "Queijo meia-cura, casquinha estalando." },
  { id: "coxinha", name: "Coxinha de Frango", cat: "Salgados", price: 8.5, unit: "un", img: "img/salgados.jpg", desc: "Recheio cremoso e massa leve." },
  { id: "empada", name: "Empada de Palmito", cat: "Salgados", price: 7.5, unit: "un", img: "img/salgados.jpg", desc: "Massa amanteigada, recheio caseiro." },
  { id: "cafe", name: "Café com Leite + Pão na Chapa", cat: "Bebidas", price: 12.9, unit: "combo", img: "img/cafe.jpg", desc: "O clássico café da manhã da Padaria Coelho." },
  { id: "cafe-puro", name: "Café Coado da Casa", cat: "Bebidas", price: 6.0, unit: "un", img: "img/cafe.jpg", desc: "Grãos torrados artesanalmente." }
];

const WHATSAPP = "5511999999999";
const STORAGE_CART = "coelho_cart";
const STORAGE_ORDERS = "coelho_orders";

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const money = (n) => n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

let PRODUCTS = FALLBACK_PRODUCTS.slice();
let cart = JSON.parse(localStorage.getItem(STORAGE_CART) || "[]");
let activeCat = "Todos";
let BAIRROS = [];
let selectedBairro = "";

function saveCart() {
  localStorage.setItem(STORAGE_CART, JSON.stringify(cart));
  renderCart();
}

function stockOf(id) {
  const p = PRODUCTS.find((x) => x.id === id);
  return p && p.stock != null ? Number(p.stock) : 99;
}

function addToCart(id) {
  const found = cart.find((i) => i.id === id);
  const next = (found ? found.qty : 0) + 1;
  if (next > stockOf(id)) return toast("Só temos " + stockOf(id) + " deste item hoje");
  if (found) found.qty += 1;
  else cart.push({ id, qty: 1 });
  saveCart();
  toast("Adicionado ao pedido");
  window.CoelhoUI && CoelhoUI.playNotify("ok");
}

function changeQty(id, delta) {
  const item = cart.find((i) => i.id === id);
  if (!item) return;
  if (delta > 0 && item.qty + delta > stockOf(id)) return toast("Estoque do dia esgotou");
  item.qty += delta;
  if (item.qty <= 0) cart = cart.filter((i) => i.id !== id);
  saveCart();
}

function cartSubtotal() {
  return cart.reduce((sum, i) => {
    const p = PRODUCTS.find((x) => x.id === i.id);
    return sum + (p ? p.price * i.qty : 0);
  }, 0);
}

function taxaAtual() {
  const tipo = document.querySelector('#checkoutForm [name="tipo"]')?.value;
  if (tipo !== "entrega") return 0;
  const b = BAIRROS.find((x) => x.id === selectedBairro);
  return b ? Number(b.taxa) : 0;
}

function cartTotal() {
  return cartSubtotal() + taxaAtual();
}

function toast(msg) {
  const el = $("#toast");
  el.textContent = msg;
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 2200);
}

function renderProducts() {
  const q = ($("#search")?.value || "").toLowerCase();
  const list = PRODUCTS.filter((p) => {
    const catOk = activeCat === "Todos" || p.cat === activeCat;
    const qOk = !q || p.name.toLowerCase().includes(q) || p.desc.toLowerCase().includes(q);
    return catOk && qOk;
  });
  $("#catalog").innerHTML = list.map((p) => `
    <article class="card">
      <img src="${p.img}" alt="${p.name}">
      <div class="card-body">
        <span class="tag">${p.cat}</span>
        <h3>${p.name}</h3>
        <p class="muted">${p.desc}</p>
        <div class="price-row">
          <span class="price">${money(p.price)} <small class="muted">/${p.unit}</small></span>
          ${(p.stock ?? 99) <= 0 ? '<button class="btn btn-ghost" disabled>Esgotado</button>' : `<button class="btn btn-dark" onclick="addToCart('${p.id}')">Pedir</button>`}
        </div>
        <p class="muted" style="margin:8px 0 0;font-size:.8rem">${(p.stock ?? 99) <= 0 ? "Acabou hoje" : "Restam " + (p.stock ?? 99) + " hoje"}</p>
      </div>
    </article>
  `).join("") || `<p class="muted">Nenhum produto encontrado.</p>`;
}

function renderPills() {
  const cats = ["Todos", ...new Set(PRODUCTS.map((p) => p.cat))];
  $("#pills").innerHTML = cats.map((c) =>
    `<button class="pill ${c === activeCat ? "active" : ""}" data-cat="${c}">${c}</button>`
  ).join("");
}

function renderCart() {
  const count = cart.reduce((n, i) => n + i.qty, 0);
  $("#cartCount").textContent = count;
  const body = $("#cartItems");
  if (!cart.length) {
    body.innerHTML = `<p class="muted">Seu cesto ainda está vazio. Escolha um pão quentinho.</p>`;
  } else {
    body.innerHTML = cart.map((i) => {
      const p = PRODUCTS.find((x) => x.id === i.id);
      return `
        <div class="cart-item">
          <img src="${p.img}" alt="${p.name}">
          <div>
            <strong>${p.name}</strong>
            <div class="muted">${money(p.price)} · ${p.unit}</div>
            <div class="qty">
              <button onclick="changeQty('${p.id}', -1)">−</button>
              <span>${i.qty}</span>
              <button onclick="changeQty('${p.id}', 1)">+</button>
            </div>
          </div>
          <strong>${money(p.price * i.qty)}</strong>
        </div>`;
    }).join("");
  }
  const taxa = taxaAtual();
  $("#cartTotal").textContent = money(cartTotal());
  const note = document.getElementById("entregaNote");
  if (note) note.textContent = taxa ? "Inclui entrega " + money(taxa) : "Retirada sem taxa";
}

function openCart(open = true) {
  $("#overlay").classList.toggle("open", open);
  $("#drawer").classList.toggle("open", open);
}

let pixPoll = null;

function saveLocalOrder(data, extra) {
  const order = {
    id: extra?.id || ("COE-" + Date.now().toString().slice(-6)),
    createdAt: new Date().toISOString(),
    status: extra?.status || "aguardando_pix",
    pagamento: extra?.id || null,
    customer: data,
    items: cart.map((i) => {
      const p = PRODUCTS.find((x) => x.id === i.id);
      return { id: p.id, name: p.name, qty: i.qty, price: p.price };
    }),
    total: extra?.valor || cartTotal()
  };
  const orders = JSON.parse(localStorage.getItem(STORAGE_ORDERS) || "[]");
  orders.unshift(order);
  localStorage.setItem(STORAGE_ORDERS, JSON.stringify(orders));
  return order;
}

function showPix(pay) {
  const modal = document.getElementById("pixModal");
  if (!modal) return;
  document.getElementById("pixStatus").textContent = pay.status === "pago" ? "Pagamento confirmado" : "Aguardando pagamento · " + pay.id;
  document.getElementById("pixValor").textContent = money(pay.valor) + " · expira com o código";
  document.getElementById("pixCopia").value = pay.copia_cola || "";
  const box = document.getElementById("pixQr");
  box.innerHTML = pay.qr_svg || "";
  modal.hidden = false;
}

async function placeOrder(e) {
  e.preventDefault();
  if (!cart.length) return toast("Adicione itens ao pedido");
  const data = Object.fromEntries(new FormData(e.target).entries());
  try {
    if (!window.CoelhoAPI) throw new Error("API");
    const pay = await CoelhoAPI.criarPix({
      nome: data.nome,
      telefone: data.telefone,
      tipo: data.tipo,
      bairro: data.bairro || selectedBairro,
      nonce: (crypto.randomUUID && crypto.randomUUID()) || String(Date.now()),
      itens: cart.map((i) => ({ id: i.id, qtd: i.qty }))
    });
    saveLocalOrder(data, pay);
    showPix(pay);
    openCart(false);
    cart = [];
    saveCart();
    e.target.reset();
    toast("PIX gerado com valor conferido no servidor");
    window.CoelhoUI && CoelhoUI.playNotify("pedido");
    CoelhoAPI.enviarWhatsapp("pedido", {
      nome: data.nome,
      telefone: data.telefone,
      tipo: data.tipo,
      pedido: pay.id,
      pix: pay.id,
      itens: (pay.itens || []).map((i) => ({ nome: i.nome, qtd: i.qtd }))
    }).then((wa) => { if (wa?.link) window.open(wa.link, "_blank"); }).catch(() => {});
    if (pixPoll) clearInterval(pixPoll);
    pixPoll = setInterval(async () => {
      try {
        const fresh = await CoelhoAPI.statusPix(pay.id, pay.consulta);
        if (fresh.status === "pago") {
          document.getElementById("pixStatus").textContent = "Pago · pedido liberado";
          window.CoelhoUI && CoelhoUI.playNotify("pedido");
          clearInterval(pixPoll);
        }
        if (fresh.status === "expirado") {
          document.getElementById("pixStatus").textContent = "PIX expirado. Faça um novo pedido.";
          clearInterval(pixPoll);
        }
      } catch {
        /* ignore */
      }
    }, 4000);
  } catch (err) {
    const order = saveLocalOrder(data, null);
    const lines = order.items.map((i) => `• ${i.qty}x ${i.name} — ${money(i.price * i.qty)}`).join("%0A");
    const msg = `Olá, Padaria Coelho! Quero confirmar o pedido ${order.id}%0A${lines}%0ATotal: ${money(order.total)}%0ANome: ${data.nome}%0ARetirada/entrega: ${data.tipo}`;
    cart = [];
    saveCart();
    e.target.reset();
    openCart(false);
    toast("API PIX offline. Encaminhando pedido no WhatsApp...");
    try {
      const wa = await CoelhoAPI.enviarWhatsapp("pedido", {
        nome: data.nome, telefone: data.telefone, tipo: data.tipo, pedido: order.id,
        itens: order.items.map((i) => ({ nome: i.name, qtd: i.qty }))
      });
      window.open(wa.link, "_blank");
    } catch {
      window.open(`https://wa.me/${WHATSAPP}?text=${msg}`, "_blank");
    }
  }
}

async function sendContact(e) {
  e.preventDefault();
  const data = Object.fromEntries(new FormData(e.target).entries());
  try {
    const wa = await CoelhoAPI.enviarWhatsapp("contato", data);
    toast("Mensagem pronta no WhatsApp");
    window.CoelhoUI && CoelhoUI.playNotify("ok");
    window.open(wa.link, "_blank");
    e.target.reset();
  } catch (err) {
    toast(err.message || "Não foi possível abrir o WhatsApp");
  }
}

async function loadFromApi() {
  if (!window.CoelhoAPI) return;
  try {
    const list = await CoelhoAPI.carregarProdutos();
    if (list.length) PRODUCTS = list;
  } catch (err) {
    console.warn("API offline, usando cardápio local", err);
  }
}

async function loadBairros() {
  const sel = document.getElementById("bairroSelect");
  if (!sel || !window.CoelhoAPI) return;
  try {
    BAIRROS = await CoelhoAPI.carregarBairros();
  } catch {
    BAIRROS = [];
  }
  sel.innerHTML = '<option value="">Bairro da entrega</option>' + BAIRROS.map((b) =>
    `<option value="${b.id}">${b.nome} · taxa ${money(b.taxa)} · mín. ${money(b.minimo)}</option>`
  ).join("");
}

function toggleBairro() {
  const tipo = document.querySelector('#checkoutForm [name="tipo"]')?.value;
  const wrap = document.getElementById("bairroWrap");
  if (wrap) wrap.hidden = tipo !== "entrega";
  renderCart();
}

document.addEventListener("DOMContentLoaded", async () => {
  if ($("#catalog")) {
    await loadFromApi();
    await loadBairros();
    renderPills();
    renderProducts();
    renderCart();
    $("#pills").addEventListener("click", (e) => {
      const btn = e.target.closest("[data-cat]");
      if (!btn) return;
      activeCat = btn.dataset.cat;
      renderPills();
      renderProducts();
    });
    $("#search")?.addEventListener("input", renderProducts);
    $("#openCart")?.addEventListener("click", () => openCart(true));
    $("#closeCart")?.addEventListener("click", () => openCart(false));
    $("#overlay")?.addEventListener("click", () => openCart(false));
    $("#checkoutForm")?.addEventListener("submit", placeOrder);
    document.querySelector('#checkoutForm [name="tipo"]')?.addEventListener("change", toggleBairro);
    document.getElementById("bairroSelect")?.addEventListener("change", (e) => {
      selectedBairro = e.target.value;
      renderCart();
    });
    $("#contactForm")?.addEventListener("submit", sendContact);
    $("#menuToggle")?.addEventListener("click", () => $("#nav").classList.toggle("open"));
    document.getElementById("pixClose")?.addEventListener("click", () => {
      document.getElementById("pixModal").hidden = true;
    });
    document.getElementById("pixCopy")?.addEventListener("click", async () => {
      const txt = document.getElementById("pixCopia").value;
      try {
        await navigator.clipboard.writeText(txt);
        toast("Código PIX copiado");
      } catch {
        document.getElementById("pixCopia").select();
      }
    });
  }
});
