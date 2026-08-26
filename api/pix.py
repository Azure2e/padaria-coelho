"""PIX EMV (BR Code) + QR SVG sem dependências externas."""

from __future__ import annotations

import html


def _tlv(tag: str, value: str) -> str:
    return f"{tag}{len(value):02d}{value}"


def crc16(data: str) -> str:
    crc = 0xFFFF
    for byte in data.encode("utf-8"):
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return f"{crc:04X}"


def br_code(chave: str, nome: str, cidade: str, valor: float, txid: str) -> str:
    nome = (nome or "PADARIA COELHO")[:25]
    cidade = (cidade or "SAO PAULO")[:15]
    chave = chave[:77]
    txid = re_txid(txid)
    valor_txt = f"{valor:.2f}"
    merchant = _tlv("00", "br.gov.bcb.pix") + _tlv("01", chave)
    extra = _tlv("05", txid)
    payload = (
        _tlv("00", "01")
        + _tlv("26", merchant)
        + _tlv("52", "0000")
        + _tlv("53", "986")
        + _tlv("54", valor_txt)
        + _tlv("58", "BR")
        + _tlv("59", nome)
        + _tlv("60", cidade)
        + _tlv("62", extra)
        + "6304"
    )
    return payload + crc16(payload)


def re_txid(txid: str) -> str:
    limpo = "".join(ch for ch in (txid or "") if ch.isalnum())
    return (limpo[:25] or "PEDIDO").upper()


# --- QR Code (byte mode, ECC M, versões 3–8) ---

_EXP = [0] * 512
_LOG = [0] * 256


def _init_gf():
    x = 1
    for i in range(255):
        _EXP[i] = x
        _LOG[x] = i
        x <<= 1
        if x & 0x100:
            x ^= 0x11D
    for i in range(255, 512):
        _EXP[i] = _EXP[i - 255]


_init_gf()


def _gf_mul(a, b):
    if a == 0 or b == 0:
        return 0
    return _EXP[_LOG[a] + _LOG[b]]


def _rs_generator(degree):
    g = [1]
    for i in range(degree):
        nxt = [0] * (len(g) + 1)
        for j, coef in enumerate(g):
            nxt[j] ^= _gf_mul(coef, _EXP[i])
            nxt[j + 1] ^= coef
        g = nxt
    return g


def _rs_encode(data, degree):
    gen = _rs_generator(degree)
    ecc = [0] * degree
    for byte in data:
        factor = byte ^ ecc[0]
        ecc = ecc[1:] + [0]
        for i, coef in enumerate(gen[1:]):
            ecc[i] ^= _gf_mul(coef, factor)
    return ecc


# versão: size, cap bytes ECC-M, ecc bytes per block, blocks
_VERSIONS = {
    3: (29, 44, 26, 1),
    4: (33, 64, 18, 2),
    5: (37, 86, 24, 2),
    6: (41, 108, 16, 4),
    7: (45, 124, 18, 4),
    8: (49, 154, 22, 4),
}


def _choose_version(nbytes):
    for ver, (_size, cap, _ecc, _blocks) in _VERSIONS.items():
        if nbytes + 2 <= cap:  # mode+len overhead already in nbytes
            return ver
    return 8


def _bits_to_bytes(bits):
    pad = (8 - len(bits) % 8) % 8
    bits += "0" * pad
    return [int(bits[i : i + 8], 2) for i in range(0, len(bits), 8)]


def _reserve(size):
    reserved = [[False] * size for _ in range(size)]

    def mark(r, c):
        if 0 <= r < size and 0 <= c < size:
            reserved[r][c] = True

    for r in range(9):
        for c in range(9):
            mark(r, c)
            mark(r, size - 8 + c - 1) if c < 8 else None
            mark(size - 8 + r - 1, c) if r < 8 else None
    for i in range(8):
        mark(i, 8)
        mark(8, i)
        mark(size - 1 - i, 8)
        mark(8, size - 1 - i)
    mark(8, 8)
    for i in range(size):
        mark(6, i)
        mark(i, 6)
    if size >= 25:
        r0 = size - 9
        for r in range(r0, r0 + 5):
            for c in range(r0, r0 + 5):
                mark(r, c)
    return reserved


def _finder(mod, r0, c0):
    pattern = [
        "1111111",
        "1000001",
        "1011101",
        "1011101",
        "1011101",
        "1000001",
        "1111111",
    ]
    for r, row in enumerate(pattern):
        for c, ch in enumerate(row):
            mod[r0 + r][c0 + c] = ch == "1"


def _timing_and_dark(mod):
    size = len(mod)
    for i in range(size):
        mod[6][i] = i % 2 == 0
        mod[i][6] = i % 2 == 0
    mod[size - 8][8] = True


def _apply_mask(mod, reserved, mask_id):
    size = len(mod)
    out = [row[:] for row in mod]
    for r in range(size):
        for c in range(size):
            if reserved[r][c]:
                continue
            bit = False
            if mask_id == 0:
                bit = (r + c) % 2 == 0
            elif mask_id == 1:
                bit = r % 2 == 0
            if bit:
                out[r][c] = not out[r][c]
    return out


def qr_modules(data: str):
    raw = data.encode("utf-8")
    ver = _choose_version(len(raw) + 2)
    size, cap, ecc_len, blocks = _VERSIONS[ver]
    bits = "0100" + f"{len(raw):08b}"
    for b in raw:
        bits += f"{b:08b}"
    bits += "0000"
    data_bytes = _bits_to_bytes(bits)
    pad = [0xEC, 0x11]
    i = 0
    while len(data_bytes) < cap:
        data_bytes.append(pad[i % 2])
        i += 1
    data_bytes = data_bytes[:cap]
    block_len = cap // blocks
    extra = cap % blocks
    ecc_all = []
    pos = 0
    chunks = []
    for b in range(blocks):
        ln = block_len + (1 if b >= blocks - extra else 0)
        chunk = data_bytes[pos : pos + ln]
        pos += ln
        chunks.append(chunk)
        ecc_all.append(_rs_encode(chunk, ecc_len))
    interleaved = []
    for i in range(max(len(c) for c in chunks)):
        for chunk in chunks:
            if i < len(chunk):
                interleaved.append(chunk[i])
    for i in range(ecc_len):
        for ecc in ecc_all:
            interleaved.append(ecc[i])
    stream = "".join(f"{b:08b}" for b in interleaved)
    reserved = _reserve(size)
    mod = [[False] * size for _ in range(size)]
    _finder(mod, 0, 0)
    _finder(mod, 0, size - 7)
    _finder(mod, size - 7, 0)
    _timing_and_dark(mod)
    idx = 0
    c = size - 1
    upward = True
    while c > 0:
        if c == 6:
            c -= 1
        rows = range(size - 1, -1, -1) if upward else range(size)
        for r in rows:
            for dc in (0, -1):
                cc = c + dc
                if reserved[r][cc]:
                    continue
                if idx < len(stream):
                    mod[r][cc] = stream[idx] == "1"
                    idx += 1
        upward = not upward
        c -= 2
    return _apply_mask(mod, reserved, 0)


def qr_svg(data: str, scale=8) -> str:
    grid = qr_modules(data)
    size = len(grid)
    quiet = 4
    dim = (size + quiet * 2) * scale
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {dim} {dim}" width="{dim}" height="{dim}" shape-rendering="crispEdges">',
        f'<rect width="{dim}" height="{dim}" fill="#fff"/>',
    ]
    for r, row in enumerate(grid):
        for c, on in enumerate(row):
            if on:
                x = (c + quiet) * scale
                y = (r + quiet) * scale
                parts.append(f'<rect x="{x}" y="{y}" width="{scale}" height="{scale}" fill="#111"/>')
    parts.append("</svg>")
    return "".join(parts)


def qr_data_uri(data: str) -> str:
    svg = qr_svg(data)
    return "data:image/svg+xml;utf8," + html.escape(svg).replace('"', "'")
