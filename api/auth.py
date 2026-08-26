"""Login, senha com hash e tokens da API Padaria Coelho."""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

DIR = Path(__file__).resolve().parent
USERS_FILE = DIR / "usuarios.json"
TOKENS_FILE = DIR / "tokens.json"
TOKEN_HOURS = 8
DEFAULT_USER = "admin"
DEFAULT_PASS = "coelho1000"


def _now():
    return datetime.now(timezone.utc)


def _iso(dt):
    return dt.astimezone(timezone.utc).isoformat()


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return salt, digest.hex()


def check_password(password: str, salt: str, stored: str) -> bool:
    _, digest = hash_password(password, salt)
    return secrets.compare_digest(digest, stored)


def load_users():
    if not USERS_FILE.exists():
        salt, digest = hash_password(DEFAULT_PASS)
        data = {
            "usuarios": [
                {
                    "usuario": DEFAULT_USER,
                    "nome": "Administrador",
                    "papel": "admin",
                    "salt": salt,
                    "senha_hash": digest,
                }
            ]
        }
        USERS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return data
    return json.loads(USERS_FILE.read_text(encoding="utf-8"))


def load_tokens():
    if not TOKENS_FILE.exists():
        return {"tokens": []}
    return json.loads(TOKENS_FILE.read_text(encoding="utf-8"))


def save_tokens(data):
    TOKENS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def purge_expired(data=None):
    data = data or load_tokens()
    now = _now()
    keep = []
    for item in data.get("tokens", []):
        try:
            exp = datetime.fromisoformat(item["expira"])
        except ValueError:
            continue
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp > now:
            keep.append(item)
    data["tokens"] = keep
    save_tokens(data)
    return data


def authenticate(usuario: str, senha: str):
    usuario = (usuario or "").strip()
    senha = senha or ""
    for user in load_users().get("usuarios", []):
        if user.get("usuario") != usuario:
            continue
        if not check_password(senha, user.get("salt", ""), user.get("senha_hash", "")):
            return None
        return {"usuario": user["usuario"], "nome": user.get("nome", usuario), "papel": user.get("papel", "admin")}
    return None


def issue_token(user: dict) -> dict:
    data = purge_expired()
    token = secrets.token_urlsafe(32)
    expira = _now() + timedelta(hours=TOKEN_HOURS)
    record = {
        "token": token,
        "usuario": user["usuario"],
        "nome": user["nome"],
        "papel": user["papel"],
        "criado": _iso(_now()),
        "expira": _iso(expira),
    }
    data["tokens"].append(record)
    save_tokens(data)
    return record


def revoke_token(token: str) -> bool:
    data = load_tokens()
    before = len(data.get("tokens", []))
    data["tokens"] = [t for t in data.get("tokens", []) if t.get("token") != token]
    save_tokens(data)
    return len(data["tokens"]) < before


def session_from_header(header: str | None, query_token: str | None = None):
    token = None
    if header:
        raw = header.strip()
        if raw.lower().startswith("bearer "):
            token = raw[7:].strip()
        else:
            token = raw
    token = token or query_token
    if not token:
        return None
    data = purge_expired()
    found = next((t for t in data["tokens"] if t.get("token") == token), None)
    return found
