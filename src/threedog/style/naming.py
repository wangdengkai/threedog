from __future__ import annotations

import unicodedata

from threedog.style.profile import NamingSpec

INVALID = '<>:"/\\|?*'
RESERVED = {"CON", "PRN", "AUX", "NUL",
            *(f"COM{i}" for i in range(1, 10)),
            *(f"LPT{i}" for i in range(1, 10))}


def sanitize(name: str) -> str:
    name = unicodedata.normalize("NFC", name)
    name = "".join(c for c in name if c not in INVALID).strip().rstrip(". ")
    if name.upper() in RESERVED:
        name = "_" + name
    return name or "_"


def display_name(name_raw: str, naming: NamingSpec, index: int = 0) -> str:
    n = sanitize(name_raw)
    if naming.convention == "emoji":
        return f"{naming.emoji_map.get(name_raw, '📁')}{n}"
    if naming.convention == "numbered":
        return f"{index:0{naming.number_width}d}-{n}"
    if naming.convention == "bilingual":
        en = naming.en_map.get(name_raw)
        return f"{en}-{n}" if en else n
    return n
