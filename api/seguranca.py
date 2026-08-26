"""Módulo de segurança da API: HMAC, rate limit, auditoria e validação."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

DIR = Path(__file__).resolve().parent
SECRET_FILE = DIR / "segredo.key"
AUDIT_FILE = DIR / "auditoria.jsonl"
PAY_FILE = DIR / "pagamentos.json"

MAX_ITENS = 40
MAX_QTD = 99
MAX_VALOR = 2000.0
PIX_MINUTOS = 15
RATE_JANELA = 600
RATE_LIMITE = 12


def secret() -> bytes:
    if not SECRET_FILE.exists():
        SECRET_FILE.write_text(secrets.token_hex(32), encoding="utf-8")
        try:
            SECRET_FILE.chmod(0o600)
        except OSError:
            pass
    return SECRET_FILE.read_text(encoding="utf-8").strip().encode("utf-8")


def assinar(texto: str) -> str:
    return hmac.new(secret(), texto.encode("utf-8"), hashlib.sha256).hexdigest()


def assinatura_ok(texto: str, assinatura: str) -> bool:
    if not assinatura:
        return False
    esperado = assinar(texto)
    return hmac.compare_digest(esperado, assinatura)


def agora_iso():
    return datetime.now(timezone.utc).isoformat()


def sanitizar(texto: str, limite=80) -> str:
    limpo = re.sub(r"[\x00-\x1f<>]", "", str(texto or "")).strip()
    return limpo[:limite]


def nonce_ok(nonce: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9_-]{8,64}", nonce or ""))


_hits: dict[str, deque] = defaultdict(deque)


def rate_ok(ip: str, rota: str) -> bool:
    chave = f"{ip}|{rota}"
    fila = _hits[chave]
    agora = time.time()
    while fila and agora - fila[0] > RATE_JANELA:
        fila.popleft()
    if len(fila) >= RATE_LIMITE:
        return False
    fila.append(agora)
    return True


def auditar(evento: str, **dados):
    linha = {"em": agora_iso(), "evento": evento, **dados}
    with AUDIT_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(linha, ensure_ascii=False) + "\n")


def load_pays():
    if not PAY_FILE.exists():
        return {"pagamentos": []}
    return json.loads(PAY_FILE.read_text(encoding="utf-8"))


def save_pays(db):
    PAY_FILE.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")
