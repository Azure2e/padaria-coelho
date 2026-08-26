"""Estoque do dia, entrega por bairro e relatório."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

DIR = Path(__file__).resolve().parent
DATA = DIR / "produtos.json"
BAIRROS = DIR / "bairros.json"
PAY = DIR / "pagamentos.json"
WA = DIR / "whatsapp.json"

DEFAULT_STOCK = {
    "pao-frances": 80,
    "pao-caseiro": 20,
    "croissant": 25,
    "pastel-carne": 30,
    "pastel-queijo": 30,
    "pastel-palmito": 20,
    "coxinha": 28,
    "cafe-puro": 40,
    "cafe": 35,
    "suco-laranja": 25,
    "pao-de-milho": 18,
}


def _load(path, fallback):
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def load_produtos():
    return _load(DATA, {"produtos": []})


def save_produtos(db):
    DATA.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")


def estoque_de(prod):
    if prod.get("estoque") is None:
        return 99
    return int(prod.get("estoque") or 0)


def garantir_estoque(produtos):
    mudou = False
    for p in produtos:
        if "estoque" not in p:
            p["estoque"] = DEFAULT_STOCK.get(p["id"], 20)
            p["estoque_base"] = p["estoque"]
            mudou = True
        if "estoque_base" not in p:
            p["estoque_base"] = p["estoque"]
            mudou = True
    return mudou


def listar_bairros():
    data = _load(BAIRROS, {"bairros": []})
    return [b for b in data.get("bairros", []) if b.get("ativo", True)]


def taxa_entrega(tipo: str, bairro_id: str, subtotal: float):
    tipo = (tipo or "retirada").lower()
    if tipo != "entrega":
        return {"tipo": "retirada", "bairro": None, "taxa": 0.0, "minimo": 0.0}
    wanted = (bairro_id or "").strip()
    bairro = next((b for b in listar_bairros() if b["id"] == wanted), None)
    if not bairro:
        raise ValueError("Escolha um bairro de entrega")
    if subtotal < float(bairro.get("minimo") or 0):
        raise ValueError(f"Pedido mínimo para {bairro['nome']}: R$ {float(bairro['minimo']):.2f}")
    return {
        "tipo": "entrega",
        "bairro": bairro["nome"],
        "bairro_id": bairro["id"],
        "taxa": round(float(bairro["taxa"]), 2),
        "minimo": float(bairro.get("minimo") or 0),
    }


def reservar(itens):
    db = load_produtos()
    mapa = {p["id"]: p for p in db["produtos"]}
    for item in itens:
        prod = mapa.get(item["id"])
        if not prod:
            raise ValueError("Produto sumiu do estoque")
        atual = estoque_de(prod)
        if atual < item["qtd"]:
            raise ValueError(f"{prod['nome']} tem só {atual} un. hoje")
        prod["estoque"] = atual - item["qtd"]
    save_produtos(db)


def devolver(itens):
    db = load_produtos()
    mapa = {p["id"]: p for p in db["produtos"]}
    for item in itens:
        prod = mapa.get(item["id"])
        if not prod:
            continue
        prod["estoque"] = estoque_de(prod) + int(item.get("qtd") or 0)
    save_produtos(db)


def repor_dia():
    db = load_produtos()
    for p in db["produtos"]:
        base = int(p.get("estoque_base") or DEFAULT_STOCK.get(p["id"], 20))
        p["estoque_base"] = base
        p["estoque"] = base
    save_produtos(db)
    return [{"id": p["id"], "nome": p["nome"], "estoque": p["estoque"]} for p in db["produtos"]]


def set_estoque(pid, qtd, base=False):
    db = load_produtos()
    prod = next((p for p in db["produtos"] if p["id"] == pid), None)
    if not prod:
        raise ValueError("Produto não encontrado")
    qtd = max(0, int(qtd))
    prod["estoque"] = qtd
    if base or "estoque_base" not in prod:
        prod["estoque_base"] = qtd
    save_produtos(db)
    return prod


def _hoje(iso):
    try:
        dt = datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return False
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).date() == now.date()


def relatorio_hoje():
    pays = _load(PAY, {"pagamentos": []}).get("pagamentos", [])
    msgs = _load(WA, {"mensagens": []}).get("mensagens", [])
    produtos = load_produtos().get("produtos", [])
    do_dia = [p for p in pays if _hoje(p.get("criado"))]
    pagos = [p for p in do_dia if p.get("status") == "pago"]
    pendentes = [p for p in do_dia if p.get("status") == "pendente"]
    faturado = round(sum(float(p.get("valor") or 0) for p in pagos), 2)
    taxas = round(sum(float((p.get("entrega") or {}).get("taxa") or 0) for p in pagos), 2)
    vendidos = {}
    horas = {}
    for p in pagos:
        for item in p.get("itens") or []:
            nome = item.get("nome") or item.get("id")
            vendidos[nome] = vendidos.get(nome, 0) + int(item.get("qtd") or 0)
        try:
            hora = datetime.fromisoformat(p["criado"]).strftime("%H") + "h"
        except Exception:
            hora = "--"
        horas[hora] = horas.get(hora, 0) + 1
    return {
        "data": datetime.now().strftime("%d/%m/%Y"),
        "pix_hoje": len(do_dia),
        "pix_pagos": len(pagos),
        "pix_pendentes": len(pendentes),
        "faturado": faturado,
        "taxas_entrega": taxas,
        "whatsapp_hoje": len([m for m in msgs if _hoje(m.get("criado"))]),
        "entregas": len([p for p in pagos if (p.get("entrega") or {}).get("tipo") == "entrega"]),
        "retiradas": len([p for p in pagos if (p.get("entrega") or {}).get("tipo") != "entrega"]),
        "mais_vendidos": sorted(vendidos.items(), key=lambda x: -x[1])[:8],
        "por_hora": sorted(horas.items()),
        "estoque": [
            {
                "id": p["id"],
                "nome": p["nome"],
                "estoque": estoque_de(p),
                "base": int(p.get("estoque_base") or estoque_de(p)),
            }
            for p in produtos if p.get("ativo", True)
        ],
    }
