"""Pagamentos PIX com recálculo de preço no servidor."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from operacao import devolver, reservar, taxa_entrega
from pix import br_code, qr_svg
from seguranca import (
    MAX_ITENS,
    MAX_QTD,
    MAX_VALOR,
    PIX_MINUTOS,
    assinar,
    agora_iso,
    auditar,
    load_pays,
    nonce_ok,
    sanitizar,
    save_pays,
)

PIX_CHAVE = "pix@padariacoelho.com.br"
PIX_NOME = "PADARIA COELHO"
PIX_CIDADE = "SAO PAULO"


def _expira():
    return datetime.now(timezone.utc) + timedelta(minutes=PIX_MINUTOS)


def _parse(dt):
    try:
        value = datetime.fromisoformat(dt)
    except (TypeError, ValueError):
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value


def montar_pedido(catalogo, itens_brutos):
    if not isinstance(itens_brutos, list) or not itens_brutos:
        raise ValueError("Informe os itens do pedido")
    if len(itens_brutos) > MAX_ITENS:
        raise ValueError("Muitos itens no pedido")
    mapa = {p["id"]: p for p in catalogo if p.get("ativo", True)}
    itens = []
    total = 0.0
    for bruto in itens_brutos:
        pid = sanitizar(str(bruto.get("id") or ""), 40)
        try:
            qtd = int(bruto.get("qtd") or bruto.get("qty") or 0)
        except (TypeError, ValueError):
            qtd = 0
        if qtd < 1 or qtd > MAX_QTD:
            raise ValueError(f"Quantidade inválida em {pid or 'item'}")
        prod = mapa.get(pid)
        if not prod:
            raise ValueError(f"Produto inválido: {pid}")
        estoque = int(prod["estoque"]) if prod.get("estoque") is not None else 99
        if estoque < qtd:
            raise ValueError(f"{prod['nome']} tem só {estoque} un. hoje")
        preco = round(float(prod["preco"]), 2)
        subtotal = round(preco * qtd, 2)
        total = round(total + subtotal, 2)
        itens.append({
            "id": pid,
            "nome": prod["nome"],
            "qtd": qtd,
            "preco": preco,
            "subtotal": subtotal,
        })
    if total <= 0 or total > MAX_VALOR:
        raise ValueError("Valor do PIX fora do limite")
    return itens, total


def criar_pix(catalogo, body, ip):
    nonce = body.get("nonce") or secrets.token_urlsafe(12)
    if not nonce_ok(nonce):
        raise ValueError("Nonce inválido")
    db = load_pays()
    if any(p.get("nonce") == nonce for p in db["pagamentos"]):
        raise ValueError("Pedido repetido (nonce já usado)")
    itens, subtotal = montar_pedido(catalogo, body.get("itens") or body.get("items") or [])
    tipo = sanitizar(body.get("tipo") or (body.get("cliente") or {}).get("tipo") or "retirada", 20)
    entrega = taxa_entrega(tipo, body.get("bairro") or body.get("bairro_id") or "", subtotal)
    total = round(subtotal + entrega["taxa"], 2)
    if total <= 0 or total > MAX_VALOR:
        raise ValueError("Valor do PIX fora do limite")
    cliente = {
        "nome": sanitizar(body.get("nome") or (body.get("cliente") or {}).get("nome"), 60),
        "telefone": sanitizar(body.get("telefone") or (body.get("cliente") or {}).get("telefone"), 20),
        "tipo": tipo,
        "bairro": entrega.get("bairro"),
    }
    if not cliente["nome"]:
        raise ValueError("Informe o nome")
    pay_id = "PIX-" + secrets.token_hex(4).upper()
    txid = pay_id.replace("-", "")[:25]
    consulta = secrets.token_urlsafe(18)
    copia = br_code(PIX_CHAVE, PIX_NOME, PIX_CIDADE, total, txid)
    expira = _expira()
    selo = assinar(f"{pay_id}|{total:.2f}|{txid}|{consulta}")
    rec = {
        "id": pay_id,
        "txid": txid,
        "status": "pendente",
        "valor": total,
        "subtotal": subtotal,
        "entrega": entrega,
        "itens": itens,
        "cliente": cliente,
        "estoque_reservado": True,
        "copia_cola": copia,
        "chave": PIX_CHAVE,
        "nonce": nonce,
        "consulta": consulta,
        "selo": selo,
        "ip": ip,
        "criado": agora_iso(),
        "expira": expira.isoformat(),
        "pago_em": None,
    }
    reservar(itens)
    db["pagamentos"].insert(0, rec)
    save_pays(db)
    auditar("pix_criado", id=pay_id, valor=total, ip=ip)
    return rec


def publico(rec, incluir_qr=False):
    out = {
        "id": rec["id"],
        "txid": rec["txid"],
        "status": status_atual(rec),
        "valor": rec["valor"],
        "copia_cola": rec["copia_cola"],
        "chave": rec["chave"],
        "expira": rec["expira"],
        "itens": rec["itens"],
        "cliente": rec["cliente"],
        "consulta": rec["consulta"],
        "subtotal": rec.get("subtotal", rec["valor"]),
        "entrega": rec.get("entrega") or {"tipo": "retirada", "taxa": 0},
    }
    if incluir_qr:
        out["qr_svg"] = qr_svg(rec["copia_cola"], scale=6)
    return out


def status_atual(rec):
    if rec["status"] == "pago":
        return "pago"
    if rec["status"] == "cancelado":
        return "cancelado"
    if _parse(rec["expira"]) < datetime.now(timezone.utc):
        if rec.get("estoque_reservado") and rec["status"] != "expirado":
            devolver(rec.get("itens") or [])
            rec["estoque_reservado"] = False
            rec["status"] = "expirado"
            db = load_pays()
            for i, item in enumerate(db["pagamentos"]):
                if item["id"] == rec["id"]:
                    db["pagamentos"][i] = rec
                    break
            save_pays(db)
        return "expirado"
    return rec["status"]


def obter(pay_id, consulta=None, admin=False):
    db = load_pays()
    rec = next((p for p in db["pagamentos"] if p["id"] == pay_id), None)
    if not rec:
        return None
    if not admin:
        if not consulta or consulta != rec.get("consulta"):
            raise PermissionError("Token de consulta inválido")
    return rec


def confirmar(pay_id, admin_user):
    db = load_pays()
    rec = next((p for p in db["pagamentos"] if p["id"] == pay_id), None)
    if not rec:
        raise ValueError("Pagamento não encontrado")
    st = status_atual(rec)
    if st == "expirado":
        rec["status"] = "expirado"
        save_pays(db)
        raise ValueError("PIX expirado")
    if st == "cancelado":
        raise ValueError("PIX cancelado")
    rec["status"] = "pago"
    rec["pago_em"] = agora_iso()
    rec["confirmado_por"] = admin_user
    save_pays(db)
    auditar("pix_pago", id=pay_id, por=admin_user)
    return rec


def listar():
    db = load_pays()
    return [{**publico(p), "status": status_atual(p)} for p in db["pagamentos"][:80]]
