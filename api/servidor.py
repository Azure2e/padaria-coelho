#!/usr/bin/env python3
"""API da Padaria Coelho — produtos e preços."""

from __future__ import annotations

import json
import re
import uuid
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from auth import authenticate, issue_token, revoke_token, session_from_header
from pagamentos import confirmar, criar_pix, listar, obter, publico
from whatsapp import contato as wa_contato, listar as wa_listar, pedido as wa_pedido
from pix import qr_svg
from seguranca import auditar, rate_ok, sanitizar
from operacao import listar_bairros, relatorio_hoje, repor_dia, set_estoque
from logs import escrever as log_write, ler as log_ler, rotacionar as log_rotacionar, salvar_config as log_salvar, status as log_status

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(__file__).resolve().parent / "produtos.json"
CATEGORIAS = ("Pães", "Pastéis", "Bebidas")
PORT = 8765


def load_db():
    if not DATA.exists():
        return {"produtos": []}
    return json.loads(DATA.read_text(encoding="utf-8"))


def save_db(db):
    DATA.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")


def slug(text: str) -> str:
    text = (text or "").strip().lower()
    table = str.maketrans("áàâãéêíóôõúç ", "aaaaeeiooouc-")
    text = text.translate(table)
    text = re.sub(r"[^a-z0-9-]+", "", text)
    return text or f"item-{uuid.uuid4().hex[:6]}"


def norm_cat(value: str) -> str:
    raw = (value or "").strip()
    mapa = {
        "pao": "Pães",
        "pão": "Pães",
        "paes": "Pães",
        "pães": "Pães",
        "pastel": "Pastéis",
        "pasteis": "Pastéis",
        "pastéis": "Pastéis",
        "bebida": "Bebidas",
        "bebidas": "Bebidas",
    }
    return mapa.get(raw.lower(), raw if raw in CATEGORIAS else raw.title())


def to_public(item: dict) -> dict:
    return {
        "id": item["id"],
        "nome": item["nome"],
        "name": item["nome"],
        "categoria": item["categoria"],
        "cat": item["categoria"],
        "preco": float(item["preco"]),
        "price": float(item["preco"]),
        "unidade": item.get("unidade", "un"),
        "unit": item.get("unidade", "un"),
        "imagem": item.get("imagem", "img/pao-frances.jpg"),
        "img": item.get("imagem", "img/pao-frances.jpg"),
        "descricao": item.get("descricao", ""),
        "desc": item.get("descricao", ""),
        "ativo": bool(item.get("ativo", True)),
        "estoque": int(item["estoque"]) if item.get("estoque") is not None else 99,
        "estoque_base": int(item.get("estoque_base") or item.get("estoque") or 99),
    }


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
        if self.path.startswith("/api/"):
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,PATCH,DELETE,OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-API-Token")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Coelho-Security", "pix-hmac+rate-limit")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def json_body(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        if not length:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw or "{}")

    def current_session(self):
        header = self.headers.get("Authorization") or self.headers.get("X-API-Token")
        qs = parse_qs(urlparse(self.path).query)
        query_token = (qs.get("token") or [None])[0]
        return session_from_header(header, query_token)

    def require_auth(self):
        sess = self.current_session()
        if sess:
            return sess
        self.send_json({"ok": False, "erro": "Faça login. Envie Authorization: Bearer TOKEN"}, 401)
        return None

    def send_json(self, payload, status=200):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/produtos":
            db = load_db()
            items = [to_public(p) for p in db["produtos"] if p.get("ativo", True)]
            qs = parse_qs(parsed.query)
            cat = qs.get("categoria", [None])[0]
            if cat:
                wanted = norm_cat(cat)
                items = [p for p in items if p["categoria"] == wanted]
            return self.send_json({"ok": True, "total": len(items), "categorias": list(CATEGORIAS), "produtos": items})
        if parsed.path == "/api/categorias":
            return self.send_json({"ok": True, "categorias": list(CATEGORIAS)})
        if parsed.path.startswith("/api/produtos/"):
            pid = parsed.path.split("/")[-1]
            db = load_db()
            item = next((p for p in db["produtos"] if p["id"] == pid), None)
            if not item:
                return self.send_json({"ok": False, "erro": "Produto não encontrado"}, 404)
            return self.send_json({"ok": True, "produto": to_public(item)})
        if parsed.path == "/api/eu":
            sess = self.require_auth()
            if not sess:
                return
            return self.send_json({"ok": True, "usuario": sess["usuario"], "nome": sess["nome"], "papel": sess["papel"], "expira": sess["expira"]})
        if parsed.path == "/api/bairros":
            return self.send_json({"ok": True, "bairros": listar_bairros()})
        if parsed.path == "/api/logs/rotacao":
            if not self.require_auth():
                return
            return self.send_json({"ok": True, **log_status()})
        if parsed.path == "/api/logs":
            if not self.require_auth():
                return
            qs = parse_qs(parsed.query)
            n = (qs.get("linhas") or ["120"])[0]
            busca = (qs.get("q") or [""])[0]
            try:
                n = int(n)
            except ValueError:
                n = 120
            linhas = log_ler(n, busca)
            return self.send_json({"ok": True, "arquivo": "api/servidor.log", "total": len(linhas), "linhas": linhas})
        if parsed.path == "/api/relatorio":
            if not self.require_auth():
                return
            return self.send_json({"ok": True, "relatorio": relatorio_hoje()})
        if parsed.path == "/api/whatsapp":
            if not self.require_auth():
                return
            return self.send_json({"ok": True, "mensagens": wa_listar()})
        if parsed.path == "/api/pagamentos":
            if not self.require_auth():
                return
            return self.send_json({"ok": True, "pagamentos": listar()})
        if parsed.path.startswith("/api/pagamentos/pix/"):
            parts = [x for x in parsed.path.split("/") if x]
            # api pagamentos pix ID [qr]
            if len(parts) >= 4:
                pay_id = parts[3]
                qs = parse_qs(parsed.query)
                token = (qs.get("token") or [None])[0]
                admin = bool(self.current_session())
                try:
                    rec = obter(pay_id, token, admin=admin)
                except PermissionError as err:
                    return self.send_json({"ok": False, "erro": str(err)}, 403)
                if not rec:
                    return self.send_json({"ok": False, "erro": "Pagamento não encontrado"}, 404)
                if len(parts) == 5 and parts[4] == "qr":
                    svg = qr_svg(rec["copia_cola"], scale=6).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
                    self.send_header("Content-Length", str(len(svg)))
                    self.end_headers()
                    self.wfile.write(svg)
                    return
                return self.send_json({"ok": True, "pagamento": publico(rec, incluir_qr=True)})
        if parsed.path == "/api":
            return self.send_json({
                "ok": True,
                "nome": "API Padaria Coelho",
                "auth": "POST /api/login  |  Authorization: Bearer TOKEN",
                "rotas": [
                    "POST /api/login",
                    "POST /api/pagamentos/pix",
                    "GET /api/pagamentos/pix/{id}?token=",
                    "POST /api/pagamentos/pix/{id}/confirmar (auth)",
                    "GET /api/produtos",
                    "POST /api/produtos (auth)",
                    "POST /api/whatsapp/contato",
                    "POST /api/whatsapp/pedido",
                    "GET /api/whatsapp (auth)",
                ],
            })
        return super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/login":
            body = self.json_body()
            user = authenticate(body.get("usuario") or body.get("user") or "admin", body.get("senha") or body.get("password") or "")
            if not user:
                return self.send_json({"ok": False, "erro": "Usuário ou senha inválidos"}, 401)
            rec = issue_token(user)
            return self.send_json({
                "ok": True,
                "token": rec["token"],
                "tipo": "Bearer",
                "expira": rec["expira"],
                "usuario": rec["usuario"],
                "nome": rec["nome"],
                "papel": rec["papel"],
            })
        if path == "/api/logout":
            sess = self.current_session()
            if sess:
                revoke_token(sess["token"])
            return self.send_json({"ok": True})
        if path == "/api/logs/rotacionar":
            if not self.require_auth():
                return
            info = log_rotacionar("manual")
            log_write("INFO", "rotacao manual " + info.get("arquivo", ""))
            return self.send_json({"ok": True, **info})
        if path == "/api/logs/rotacao":
            if not self.require_auth():
                return
            cfg = log_salvar(self.json_body())
            log_write("INFO", "rotacao configurada " + str(cfg))
            return self.send_json({"ok": True, "config": cfg})
        if path == "/api/estoque/repor":
            if not self.require_auth():
                return
            lista = repor_dia()
            auditar("estoque_reposto")
            return self.send_json({"ok": True, "produtos": lista})
        if path == "/api/whatsapp/contato":
            ip = self.client_address[0]
            if not rate_ok(ip, "wa"):
                return self.send_json({"ok": False, "erro": "Muitas mensagens. Tente depois."}, 429)
            try:
                rec = wa_contato(self.json_body(), ip)
            except ValueError as err:
                return self.send_json({"ok": False, "erro": str(err)}, 400)
            return self.send_json({"ok": True, "whatsapp": rec}, 201)
        if path == "/api/whatsapp/pedido":
            ip = self.client_address[0]
            if not rate_ok(ip, "wa"):
                return self.send_json({"ok": False, "erro": "Muitas mensagens. Tente depois."}, 429)
            try:
                rec = wa_pedido(self.json_body(), ip)
            except ValueError as err:
                return self.send_json({"ok": False, "erro": str(err)}, 400)
            return self.send_json({"ok": True, "whatsapp": rec}, 201)
        if path == "/api/pagamentos/pix":
            ip = self.client_address[0]
            if not rate_ok(ip, "pix"):
                auditar("pix_bloqueado", ip=ip)
                return self.send_json({"ok": False, "erro": "Muitas tentativas. Aguarde alguns minutos."}, 429)
            body = self.json_body()
            try:
                rec = criar_pix(load_db()["produtos"], body, ip)
            except ValueError as err:
                return self.send_json({"ok": False, "erro": str(err)}, 400)
            return self.send_json({"ok": True, "pagamento": publico(rec, incluir_qr=True)}, 201)
        if path.startswith("/api/pagamentos/pix/") and path.endswith("/confirmar"):
            if not self.require_auth():
                return
            pay_id = path.split("/")[-2]
            try:
                rec = confirmar(pay_id, self.current_session()["usuario"])
            except ValueError as err:
                return self.send_json({"ok": False, "erro": str(err)}, 400)
            return self.send_json({"ok": True, "pagamento": publico(rec)})
        if path != "/api/produtos":
            return self.send_json({"ok": False, "erro": "Rota inválida"}, 404)
        if not self.require_auth():
            return
        body = self.json_body()
        nome = (body.get("nome") or body.get("name") or "").strip()
        if not nome:
            return self.send_json({"ok": False, "erro": "Informe o nome"}, 400)
        categoria = norm_cat(body.get("categoria") or body.get("cat") or "Pães")
        if categoria not in CATEGORIAS:
            return self.send_json({"ok": False, "erro": "Categoria deve ser Pães, Pastéis ou Bebidas"}, 400)
        try:
            preco = float(body.get("preco") if body.get("preco") is not None else body.get("price", 0))
        except (TypeError, ValueError):
            return self.send_json({"ok": False, "erro": "Preço inválido"}, 400)
        db = load_db()
        pid = slug(body.get("id") or nome)
        if any(p["id"] == pid for p in db["produtos"]):
            pid = f"{pid}-{uuid.uuid4().hex[:4]}"
        item = {
            "id": pid,
            "nome": nome,
            "categoria": categoria,
            "preco": round(preco, 2),
            "unidade": body.get("unidade") or body.get("unit") or "un",
            "imagem": body.get("imagem") or body.get("img") or default_img(categoria),
            "descricao": body.get("descricao") or body.get("desc") or "",
            "ativo": True,
            "estoque": int(body.get("estoque") or 20),
            "estoque_base": int(body.get("estoque") or 20),
        }
        db["produtos"].append(item)
        save_db(db)
        return self.send_json({"ok": True, "produto": to_public(item)}, 201)

    def do_PUT(self):
        parsed = urlparse(self.path)
        parts = parsed.path.strip("/").split("/")
        if len(parts) != 3 or parts[0] != "api" or parts[1] != "produtos":
            return self.send_json({"ok": False, "erro": "Rota inválida"}, 404)
        if not self.require_auth():
            return
        pid = parts[2]
        body = self.json_body()
        db = load_db()
        item = next((p for p in db["produtos"] if p["id"] == pid), None)
        if not item:
            return self.send_json({"ok": False, "erro": "Produto não encontrado"}, 404)
        if "nome" in body or "name" in body:
            item["nome"] = (body.get("nome") or body.get("name")).strip()
        if "categoria" in body or "cat" in body:
            cat = norm_cat(body.get("categoria") or body.get("cat"))
            if cat not in CATEGORIAS:
                return self.send_json({"ok": False, "erro": "Categoria deve ser Pães, Pastéis ou Bebidas"}, 400)
            item["categoria"] = cat
        if "preco" in body or "price" in body:
            try:
                item["preco"] = round(float(body.get("preco") if body.get("preco") is not None else body.get("price")), 2)
            except (TypeError, ValueError):
                return self.send_json({"ok": False, "erro": "Preço inválido"}, 400)
        if "unidade" in body or "unit" in body:
            item["unidade"] = body.get("unidade") or body.get("unit")
        if "descricao" in body or "desc" in body:
            item["descricao"] = body.get("descricao") or body.get("desc")
        if "imagem" in body or "img" in body:
            item["imagem"] = body.get("imagem") or body.get("img")
        if "ativo" in body:
            item["ativo"] = bool(body["ativo"])
        save_db(db)
        return self.send_json({"ok": True, "produto": to_public(item)})

    def do_PATCH(self):
        parsed = urlparse(self.path)
        parts = parsed.path.strip("/").split("/")
        if len(parts) != 4 or parts[0] != "api" or parts[1] != "produtos" or parts[3] not in ("preco", "estoque"):
            return self.send_json({"ok": False, "erro": "Use PATCH /api/produtos/{id}/preco ou /estoque"}, 404)
        if not self.require_auth():
            return
        if parts[3] == "estoque":
            body = self.json_body()
            try:
                prod = set_estoque(parts[2], body.get("estoque") if body.get("estoque") is not None else body.get("qtd"), base=bool(body.get("base")))
            except ValueError as err:
                return self.send_json({"ok": False, "erro": str(err)}, 400)
            return self.send_json({"ok": True, "produto": to_public(prod)})
        pid = parts[2]
        body = self.json_body()
        try:
            preco = float(body.get("preco") if body.get("preco") is not None else body.get("price"))
        except (TypeError, ValueError):
            return self.send_json({"ok": False, "erro": "Informe o novo preço"}, 400)
        db = load_db()
        item = next((p for p in db["produtos"] if p["id"] == pid), None)
        if not item:
            return self.send_json({"ok": False, "erro": "Produto não encontrado"}, 404)
        antigo = item["preco"]
        item["preco"] = round(preco, 2)
        save_db(db)
        return self.send_json({"ok": True, "id": pid, "preco_antigo": antigo, "preco": item["preco"], "produto": to_public(item)})

    def do_DELETE(self):
        parsed = urlparse(self.path)
        parts = parsed.path.strip("/").split("/")
        if len(parts) != 3 or parts[0] != "api" or parts[1] != "produtos":
            return self.send_json({"ok": False, "erro": "Rota inválida"}, 404)
        if not self.require_auth():
            return
        pid = parts[2]
        db = load_db()
        item = next((p for p in db["produtos"] if p["id"] == pid), None)
        if not item:
            return self.send_json({"ok": False, "erro": "Produto não encontrado"}, 404)
        item["ativo"] = False
        save_db(db)
        return self.send_json({"ok": True, "removido": pid})

    def log_message(self, fmt, *args):
        msg = fmt % args
        if "/api/logs" in (self.path or ""):
            return
        nivel = "ERRO" if " 5" in msg or " 4" in msg else "INFO"
        log_write(nivel, msg, self.address_string())


def default_img(cat: str) -> str:
    return {
        "Pães": "img/pao-frances.jpg",
        "Pastéis": "img/salgados.jpg",
        "Bebidas": "img/cafe.jpg",
    }.get(cat, "img/pao-frances.jpg")


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    log_write("INFO", f"servidor iniciado na porta {PORT}")
    print(f"Padaria Coelho API em http://127.0.0.1:{PORT}")
    print("Site:  http://127.0.0.1:8765/index.html")
    print("API:   http://127.0.0.1:8765/api/produtos")
    print("Logs:  ./ver-logs.sh")
    server.serve_forever()
