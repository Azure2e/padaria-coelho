const STORAGE_ORDERS = "coelho_orders";
const PASS = "coelho1000";
const money = (n) => Number(n).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

function orders() {
  return JSON.parse(localStorage.getItem(STORAGE_ORDERS) || "[]");
}
function save(list) {
  localStorage.setItem(STORAGE_ORDERS, JSON.stringify(list));
}

async function login(e) {
  e.preventDefault();
  const pass = new FormData(e.target).get("senha");
  const err = document.getElementById("err");
  err.textContent = "";
  if (pass !== PASS) {
    err.textContent = "Senha incorreta.";
    return;
  }
  try {
    if (window.CoelhoAPI) await CoelhoAPI.apiLogin("admin", pass);
  } catch (ex) {
    err.textContent = "Painel ok, mas a API recusou o login: " + ex.message;
  }
  sessionStorage.setItem("coelho_admin", "1");
  showApp();
}

let lastOrderCount = orders().length;

function watchOrders() {
  const list = orders();
  if (list.length > lastOrderCount) {
    window.CoelhoUI && CoelhoUI.playNotify("pedido");
    const extra = list.length - lastOrderCount;
    const note = document.getElementById("liveNote");
    if (note) note.textContent = extra + " pedido(s) novo(s)";
  }
  lastOrderCount = list.length;
  render();
}

function showApp() {
  document.getElementById("loginBox").hidden = true;
  document.getElementById("adminApp").hidden = false;
  lastOrderCount = orders().length;
  render();
  setInterval(watchOrders, 2500);
}

function render() {
  const list = orders();
  const faturado = list.reduce((s, o) => s + Number(o.total || 0), 0);
  document.getElementById("kpiPedidos").textContent = list.length;
  document.getElementById("kpiFaturado").textContent = money(faturado);
  document.getElementById("kpiNovos").textContent = list.filter((o) => o.status === "novo").length;
  document.getElementById("rows").innerHTML = list.map((o) => `
    <tr>
      <td><strong>${o.id}</strong><br><small>${new Date(o.createdAt).toLocaleString("pt-BR")}</small></td>
      <td>${o.customer?.nome || "-"}<br><small>${o.customer?.telefone || ""} · ${o.customer?.tipo || ""}</small></td>
      <td>${(o.items || []).map((i) => `${i.qty}x ${i.name}`).join("<br>")}</td>
      <td>${money(o.total)}</td>
      <td>
        <select onchange="setStatus('${o.id}', this.value)">
          ${["novo","preparo","pronto","entregue"].map((s) =>
            `<option value="${s}" ${o.status===s?"selected":""}>${s}</option>`).join("")}
        </select>
      </td>
    </tr>
  `).join("") || `<tr><td colspan="5">Nenhum pedido ainda. Faça um pedido no site.</td></tr>`;
}

function setStatus(id, status) {
  const list = orders().map((o) => o.id === id ? { ...o, status } : o);
  save(list);
  render();
}

function seed() {
  if (orders().length) return render();
  save([{
    id: "COE-1001",
    createdAt: new Date().toISOString(),
    status: "novo",
    customer: { nome: "Maria Souza", telefone: "(11) 98888-0000", tipo: "retirada" },
    items: [{ name: "Pão Francês", qty: 10, price: 0.9 }, { name: "Café com Leite + Pão na Chapa", qty: 2, price: 12.9 }],
    total: 34.8
  }]);
  render();
}

async function logout() {
  sessionStorage.removeItem("coelho_admin");
  if (window.CoelhoAPI) await CoelhoAPI.apiLogout();
  location.reload();
}

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("loginForm").addEventListener("submit", login);
  if (sessionStorage.getItem("coelho_admin") === "1") showApp();
});

async function loadProductsAdmin() {
  const note = document.getElementById("apiNote");
  const rows = document.getElementById("productRows");
  if (!rows || !window.CoelhoAPI) return;
  try {
    const data = await CoelhoAPI.apiGet("/produtos");
    note.textContent = data.total + " itens na API";
    rows.innerHTML = (data.produtos || []).map((p) => `
      <tr>
        <td><strong>${p.nome}</strong><br><small>${p.descricao || ""}</small></td>
        <td>${p.categoria}</td>
        <td>
          <input type="number" min="0" step="0.01" value="${Number(p.preco).toFixed(2)}"
            style="width:110px" data-price="${p.id}" />
        </td>
        <td>
          <input type="number" min="0" step="1" value="${Number(p.estoque ?? 0)}"
            style="width:80px" data-stock="${p.id}" />
        </td>
        <td>
          <button class="mini" onclick="salvarPreco('${p.id}')">Preço</button>
          <button class="mini" onclick="salvarEstoque('${p.id}')">Estoque</button>
          <button class="mini" onclick="removerProduto('${p.id}')">Tirar</button>
        </td>
      </tr>
    `).join("");
  } catch (err) {
    note.textContent = "API offline. Rode: python3 api/servidor.py";
  }
}

async function salvarPreco(id) {
  const input = document.querySelector(`[data-price="${id}"]`);
  try {
    await CoelhoAPI.apiSend(`/produtos/${id}/preco`, "PATCH", { preco: Number(input.value) });
    window.CoelhoUI && CoelhoUI.playNotify("ok");
    await loadProductsAdmin();
  } catch (err) {
    alert(err.message);
  }
}

async function removerProduto(id) {
  if (!confirm("Remover este item do cardápio?")) return;
  try {
    await CoelhoAPI.apiSend(`/produtos/${id}`, "DELETE");
    await loadProductsAdmin();
  } catch (err) {
    alert(err.message);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("productForm");
  form?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(e.target).entries());
    try {
      await CoelhoAPI.apiSend("/produtos", "POST", {
        nome: data.nome,
        categoria: data.categoria,
        preco: Number(data.preco),
        unidade: data.unidade,
        descricao: data.descricao,
        estoque: Number(data.estoque || 20)
      });
      e.target.reset();
      window.CoelhoUI && CoelhoUI.playNotify("ok");
      await loadProductsAdmin();
    } catch (err) {
      alert(err.message);
    }
  });
});

const _show = showApp;
showApp = function () {
  _show();
  loadProductsAdmin();
};


async function loadPixAdmin() {
  const rows = document.getElementById("pixRows");
  if (!rows || !window.CoelhoAPI) return;
  try {
    const data = await CoelhoAPI.apiGet("/pagamentos");
    rows.innerHTML = (data.pagamentos || []).map((p) => `
      <tr>
        <td><strong>${p.id}</strong><br><small>${p.txid || ""}</small></td>
        <td>${p.cliente?.nome || "-"}<br><small>${(p.itens || []).map((i) => i.qtd + "x " + i.nome).join(", ")}</small></td>
        <td>${money(p.valor)}</td>
        <td>${p.status}</td>
        <td>${p.status === "pendente" ? `<button class="mini" onclick="confirmarPixAdmin('${p.id}')">Confirmar pagamento</button>` : ""}</td>
      </tr>
    `).join("") || `<tr><td colspan="5">Nenhum PIX ainda.</td></tr>`;
  } catch (err) {
    rows.innerHTML = `<tr><td colspan="5">Não foi possível ler os PIX.</td></tr>`;
  }
}

async function confirmarPixAdmin(id) {
  try {
    await CoelhoAPI.confirmarPix(id);
    window.CoelhoUI && CoelhoUI.playNotify("pedido");
    await loadPixAdmin();
  } catch (err) {
    alert(err.message);
  }
}

const _show2 = showApp;
showApp = function () {
  _show2();
  loadPixAdmin();
};


async function loadWaAdmin() {
  const rows = document.getElementById("waRows");
  if (!rows || !window.CoelhoAPI) return;
  try {
    const data = await CoelhoAPI.apiGet("/whatsapp");
    rows.innerHTML = (data.mensagens || []).map((m) => `
      <tr>
        <td>${m.id}</td>
        <td>${m.tipo}</td>
        <td>${m.nome}<br><small>${m.contato || ""}</small></td>
        <td><small>${(m.preview || "").replace(/</g,"")}</small></td>
        <td><a class="mini" href="${m.link}" target="_blank" rel="noopener">Abrir</a></td>
      </tr>
    `).join("") || `<tr><td colspan="5">Nenhuma mensagem ainda.</td></tr>`;
  } catch {
    rows.innerHTML = `<tr><td colspan="5">API WhatsApp indisponível.</td></tr>`;
  }
}

const _show3 = showApp;
showApp = function () {
  _show3();
  loadWaAdmin();
  loadRelatorio();
};


async function loadLogs() {
  const box = document.getElementById("logBox");
  if (!box || !window.CoelhoAPI) return;
  const q = document.getElementById("logQuery")?.value || "";
  try {
    const data = await CoelhoAPI.apiGet("/logs?linhas=150&q=" + encodeURIComponent(q));
    box.textContent = (data.linhas || []).join("\n") || "Sem linhas no log ainda.";
    box.scrollTop = box.scrollHeight;
  } catch (err) {
    box.textContent = "Não foi possível ler o log. Confira se a API está ligada.";
  }
}

const _show4 = showApp;
showApp = function () {
  _show4();
  loadLogs();
  loadLogCfg();
  setInterval(loadLogs, 4000);
};


async function loadLogCfg() {
  try {
    const data = await CoelhoAPI.apiGet("/logs/rotacao");
    const c = data.config || {};
    const set = (id, v) => { const el = document.getElementById(id); if (el) el.value = v; };
    set("logMaxMb", c.max_mb);
    set("logKeep", c.guardar);
    set("logGz", String(!!c.comprimir));
    set("logDia", String(!!c.por_dia));
    const st = document.getElementById("logStatus");
    if (st) st.textContent = `Arquivo atual ${data.atual_kb} KB / limite ${data.limite_kb} KB · ${ (data.arquivos||[]).length } arquivo(s)`;
  } catch { /* ignore */ }
}

async function girarLogs() {
  try {
    await CoelhoAPI.apiSend("/logs/rotacionar", "POST");
    await loadLogs();
    await loadLogCfg();
  } catch (err) {
    alert(err.message);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("logCfg")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await CoelhoAPI.apiSend("/logs/rotacao", "POST", {
        max_mb: Number(document.getElementById("logMaxMb").value),
        guardar: Number(document.getElementById("logKeep").value),
        comprimir: document.getElementById("logGz").value === "true",
        por_dia: document.getElementById("logDia").value === "true"
      });
      await loadLogCfg();
    } catch (err) {
      alert(err.message);
    }
  });
});
