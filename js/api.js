const API_BASE = `${location.origin}/api`;
const TOKEN_KEY = "coelho_api_token";

function apiToken() {
  return sessionStorage.getItem(TOKEN_KEY) || "";
}

function setApiToken(token) {
  if (token) sessionStorage.setItem(TOKEN_KEY, token);
  else sessionStorage.removeItem(TOKEN_KEY);
}

function authHeaders(extra = {}) {
  const headers = { ...extra };
  const token = apiToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

async function apiGet(path) {
  const res = await fetch(API_BASE + path, { headers: authHeaders() });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || data.ok === false) throw new Error(data.erro || "Falha na API");
  return data;
}

async function apiSend(path, method, body) {
  const res = await fetch(API_BASE + path, {
    method,
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: body ? JSON.stringify(body) : undefined
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || data.ok === false) throw new Error(data.erro || "Falha na API");
  return data;
}

async function apiLogin(usuario, senha) {
  const data = await apiSend("/login", "POST", { usuario, senha });
  setApiToken(data.token);
  return data;
}

async function apiLogout() {
  try {
    await apiSend("/logout", "POST");
  } catch {
    /* ignore */
  }
  setApiToken("");
}

async function carregarProdutos(categoria) {
  const qs = categoria && categoria !== "Todos" ? `?categoria=${encodeURIComponent(categoria)}` : "";
  const data = await apiGet("/produtos" + qs);
  return (data.produtos || []).map((p) => ({
    id: p.id,
    name: p.nome || p.name,
    cat: p.categoria || p.cat,
    price: Number(p.preco ?? p.price),
    unit: p.unidade || p.unit || "un",
    img: p.imagem || p.img,
    desc: p.descricao || p.desc || "",
    stock: Number(p.estoque ?? 99)
  }));
}

async function criarPix(payload) {
  const data = await apiSend("/pagamentos/pix", "POST", payload);
  return data.pagamento;
}

async function statusPix(id, token) {
  const data = await apiGet(`/pagamentos/pix/${id}?token=${encodeURIComponent(token || "")}`);
  return data.pagamento;
}

async function confirmarPix(id) {
  const data = await apiSend(`/pagamentos/pix/${id}/confirmar`, "POST");
  return data.pagamento;
}

async function enviarWhatsapp(tipo, payload) {
  const rota = tipo === "pedido" ? "/whatsapp/pedido" : "/whatsapp/contato";
  const data = await apiSend(rota, "POST", payload);
  return data.whatsapp;
}

async function carregarBairros() {
  const data = await apiGet("/bairros");
  return data.bairros || [];
}

window.CoelhoAPI = { apiGet, apiSend, apiLogin, apiLogout, carregarProdutos, carregarBairros, criarPix, statusPix, confirmarPix, enviarWhatsapp, apiToken, setApiToken };
