"""Log com rotação por tamanho e por dia."""

from __future__ import annotations

import gzip
import json
import shutil
from datetime import datetime
from pathlib import Path

DIR = Path(__file__).resolve().parent
CFG = DIR / "logs.json"
PADRAO = {
    "max_mb": 1,
    "guardar": 5,
    "comprimir": True,
    "por_dia": True,
    "arquivo": "servidor.log",
}


def config():
    data = dict(PADRAO)
    if CFG.exists():
        try:
            data.update(json.loads(CFG.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            pass
    data["max_mb"] = max(0.2, min(float(data.get("max_mb") or 1), 50))
    data["guardar"] = max(1, min(int(data.get("guardar") or 5), 20))
    data["comprimir"] = bool(data.get("comprimir", True))
    data["por_dia"] = bool(data.get("por_dia", True))
    data["arquivo"] = "servidor.log"
    return data


def salvar_config(body: dict):
    atual = config()
    if "max_mb" in body:
        atual["max_mb"] = body["max_mb"]
    if "guardar" in body:
        atual["guardar"] = body["guardar"]
    if "comprimir" in body:
        atual["comprimir"] = bool(body["comprimir"])
    if "por_dia" in body:
        atual["por_dia"] = bool(body["por_dia"])
    CFG.write_text(json.dumps({
        "max_mb": atual["max_mb"],
        "guardar": atual["guardar"],
        "comprimir": atual["comprimir"],
        "por_dia": atual["por_dia"],
        "arquivo": "servidor.log",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return config()


def arquivo():
    return DIR / config()["arquivo"]


def _agora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _stamp(path: Path):
    return datetime.fromtimestamp(path.stat().st_mtime).date()


def precisa_rotar():
    log = arquivo()
    if not log.exists() or log.stat().st_size == 0:
        return False
    cfg = config()
    if log.stat().st_size >= int(cfg["max_mb"] * 1024 * 1024):
        return True
    if cfg["por_dia"] and _stamp(log) < datetime.now().date():
        return True
    return False


def rotacionar(motivo="manual"):
    log = arquivo()
    if not log.exists():
        return {"ok": True, "motivo": motivo, "acao": "vazio"}
    cfg = config()
    guardar = cfg["guardar"]
    # empilha: .5 some, .4 -> .5 ...
    for i in range(guardar, 0, -1):
        origem = DIR / f"servidor.log.{i}"
        origem_gz = DIR / f"servidor.log.{i}.gz"
        destino = DIR / f"servidor.log.{i + 1}"
        destino_gz = DIR / f"servidor.log.{i + 1}.gz"
        if i >= guardar:
            origem.unlink(missing_ok=True)
            origem_gz.unlink(missing_ok=True)
            continue
        if origem.exists():
            destino.unlink(missing_ok=True)
            origem.rename(destino)
        if origem_gz.exists():
            destino_gz.unlink(missing_ok=True)
            origem_gz.rename(destino_gz)
    alvo = DIR / "servidor.log.1"
    if cfg["comprimir"]:
        alvo_gz = DIR / "servidor.log.1.gz"
        with log.open("rb") as src, gzip.open(alvo_gz, "wb") as dst:
            shutil.copyfileobj(src, dst)
        log.write_text("", encoding="utf-8")
        nome = alvo_gz.name
    else:
        alvo.unlink(missing_ok=True)
        log.rename(alvo)
        nome = alvo.name
    return {"ok": True, "motivo": motivo, "arquivo": nome, "config": cfg}


def arquivos_rotacionados():
    itens = []
    for path in sorted(DIR.glob("servidor.log*")):
        itens.append({
            "nome": path.name,
            "bytes": path.stat().st_size,
            "kb": round(path.stat().st_size / 1024, 1),
            "quando": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
        })
    return itens


def status():
    log = arquivo()
    cfg = config()
    tamanho = log.stat().st_size if log.exists() else 0
    return {
        "config": cfg,
        "atual_bytes": tamanho,
        "atual_kb": round(tamanho / 1024, 1),
        "limite_kb": round(cfg["max_mb"] * 1024, 1),
        "precisa_rotar": precisa_rotar(),
        "arquivos": arquivos_rotacionados(),
    }


def escrever(nivel: str, mensagem: str, ip: str = "-"):
    linha = f"{_agora()} [{nivel}] {ip} {mensagem}".replace("\n", " ")
    try:
        if precisa_rotar():
            rotacionar("automatico")
        with arquivo().open("a", encoding="utf-8") as fh:
            fh.write(linha + "\n")
    except OSError:
        pass
    print(linha, flush=True)


def ler(linhas: int = 120, busca: str = ""):
    log = arquivo()
    if not log.exists():
        return []
    linhas = max(10, min(int(linhas or 120), 500))
    texto = log.read_text(encoding="utf-8", errors="replace").splitlines()
    if busca:
        q = busca.lower()
        texto = [l for l in texto if q in l.lower()]
    return texto[-linhas:]
