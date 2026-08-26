"""Formulários encaminhados ao WhatsApp pelo backend."""

from __future__ import annotations

import json
import re
import secrets
from pathlib import Path
from urllib.parse import quote

from seguranca import agora_iso, auditar, sanitizar

DIR = Path(__file__).resolve().parent
MSG_FILE = DIR / "whatsapp.json"
NUMERO = "5511999999999"


def load_msgs():
    if not MSG_FILE.exists():
        return {"mensagens": []}
    return json.loads(MSG_FILE.read_text(encoding="utf-8"))


def save_msgs(db):
    MSG_FILE.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")


def _fone(valor: str) -> str:
    return re.sub(r"\D+", "", valor or "")[:15]


def _link(texto: str) -> str:
    return f"https://wa.me/{NUMERO}?text={quote(texto)}"


def contato(body: dict, ip: str) -> dict:
    if sanitizar(body.get("empresa") or body.get("website") or "", 40):
        raise ValueError("Requisição recusada")
    nome = sanitizar(body.get("nome"), 60)
    contato_txt = sanitizar(body.get("email") or body.get("telefone") or body.get("whatsapp"), 80)
    mensagem = sanitizar(body.get("mensagem") or body.get("texto"), 500)
    if not nome or not contato_txt or not mensagem:
        raise ValueError("Preencha nome, contato e mensagem")
    texto = (
        f"Contato pelo site Padaria Coelho\n"
        f"Nome: {nome}\n"
        f"Contato: {contato_txt}\n"
        f"Mensagem: {mensagem}"
    )
    return _gravar("contato", nome, contato_txt, texto, ip)


def pedido(body: dict, ip: str) -> dict:
    nome = sanitizar(body.get("nome"), 60)
    telefone = sanitizar(body.get("telefone"), 20)
    tipo = sanitizar(body.get("tipo") or "retirada", 20)
    pedido_id = sanitizar(body.get("pedido") or body.get("id") or "", 20)
    pix_id = sanitizar(body.get("pix") or "", 20)
    if not nome:
        raise ValueError("Informe o nome")
    itens = body.get("itens") or body.get("items") or []
    linhas = []
    for item in itens[:40]:
        qtd = item.get("qtd") or item.get("qty") or 1
        nome_item = sanitizar(item.get("nome") or item.get("name") or item.get("id"), 40)
        linhas.append(f"- {qtd}x {nome_item}")
    lista = "\n".join(linhas) or "- (itens no PIX/cardápio)"
    texto = (
        f"Pedido pelo site Padaria Coelho\n"
        f"Pedido: {pedido_id or 'novo'}\n"
        f"Nome: {nome}\n"
        f"WhatsApp: {telefone}\n"
        f"Tipo: {tipo}\n"
        f"PIX: {pix_id or '-'}\n"
        f"Itens:\n{lista}"
    )
    return _gravar("pedido", nome, telefone, texto, ip)


def _gravar(tipo: str, nome: str, contato_txt: str, texto: str, ip: str) -> dict:
    rec = {
        "id": "WA-" + secrets.token_hex(3).upper(),
        "tipo": tipo,
        "nome": nome,
        "contato": contato_txt,
        "mensagem": texto,
        "link": _link(texto),
        "numero": NUMERO,
        "ip": ip,
        "criado": agora_iso(),
    }
    db = load_msgs()
    db["mensagens"].insert(0, rec)
    save_msgs(db)
    auditar("whatsapp_" + tipo, id=rec["id"], ip=ip)
    return {
        "id": rec["id"],
        "tipo": rec["tipo"],
        "link": rec["link"],
        "numero": rec["numero"],
        "preview": texto,
    }


def listar():
    return [
        {
            "id": m["id"],
            "tipo": m["tipo"],
            "nome": m["nome"],
            "contato": m["contato"],
            "preview": m["mensagem"][:180],
            "link": m["link"],
            "criado": m["criado"],
        }
        for m in load_msgs().get("mensagens", [])[:100]
    ]
