"""Metin temizleme, slug üretme, süre/porsiyon biçimlendirme ve görsel yardımcıları."""

from __future__ import annotations

import re
import unicodedata
from typing import Optional
from urllib.parse import urljoin, urlparse

from config import BASE_URL, DEFAULT_VALUE, STOCK_IMAGE_URL_TEMPLATE

# Türkçe karakterlerin Latin karşılıkları. Büyük "İ" ve "I" harfleri
# .lower() çağrısından ÖNCE çevrilmeli; aksi halde "İ" -> "i̇" (noktalı) olur.
_TURKISH_MAP: dict[str, str] = {
    "ç": "c", "Ç": "c",
    "ğ": "g", "Ğ": "g",
    "ı": "i", "I": "i",
    "İ": "i", "i̇": "i",
    "ö": "o", "Ö": "o",
    "ş": "s", "Ş": "s",
    "ü": "u", "Ü": "u",
    "â": "a", "Â": "a",
    "î": "i", "Î": "i",
    "û": "u", "Û": "u",
}

_WHITESPACE_RE = re.compile(r"\s+")
_ISO_DURATION_RE = re.compile(
    r"^P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?$",
    re.IGNORECASE,
)
_MINUTES_TEXT_RE = re.compile(r"(\d+)\s*(dk|dakika|dak)", re.IGNORECASE)
_HOURS_TEXT_RE = re.compile(r"(\d+)\s*(saat|sa)\b", re.IGNORECASE)


def clean_text(text: Optional[str]) -> str:
    """Fazla boşlukları, satır sonlarını, \\xa0 ve görünmez karakterleri temizler."""
    if not text:
        return ""
    # Ayrık yazılmış Türkçe harfleri ("c" + birleştirici çengel) tek karaktere indir.
    text = unicodedata.normalize("NFC", text)
    text = (
        text.replace("\xa0", " ")
        .replace("​", "")
        .replace("﻿", "")
        .replace("\r", " ")
        .replace("\n", " ")
        .replace("\t", " ")
    )
    text = _WHITESPACE_RE.sub(" ", text).strip()
    # Liste işaretleri ve baştaki/sondaki gereksiz noktalama
    return text.strip(" -•*·,;")


def slugify(text: str) -> str:
    """Türkçe karakterleri doğru biçimde Latinize ederek URL dostu slug üretir.

    Örnek: "Mercimek Çorbası" -> "mercimek-corbasi"
    """
    for tr_char, latin in _TURKISH_MAP.items():
        text = text.replace(tr_char, latin)
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "tarif"


def build_image_url(title: str, index: int) -> str:
    """Görsel bulunamadığında başlığa göre deterministik bir stok görsel URL'i üretir.

    Aynı başlık ve sıra numarası her zaman aynı URL'i verir.
    """
    return STOCK_IMAGE_URL_TEMPLATE.format(slug=slugify(title), index=index)


def is_valid_image_url(url: Optional[str]) -> bool:
    """URL'in http(s) şemalı, alan adı olan gerçek bir adres olup olmadığını kontrol eder.

    Lazy-load için kullanılan "data:image/..." yer tutucuları geçersiz sayılır.
    """
    if not url or not isinstance(url, str):
        return False
    parsed = urlparse(url.strip())
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def first_url_from_srcset(srcset: str) -> str:
    """"a.jpg 300w, b.jpg 600w" biçimindeki srcset değerinden en büyük görseli seçer."""
    candidates: list[tuple[int, str]] = []
    for part in srcset.split(","):
        pieces = part.strip().split()
        if not pieces:
            continue
        width = 0
        if len(pieces) > 1 and pieces[1].rstrip("wx").isdigit():
            width = int(pieces[1].rstrip("wx"))
        candidates.append((width, pieces[0]))
    if not candidates:
        return ""
    return max(candidates, key=lambda c: c[0])[1]


def absolute_url(url: str) -> str:
    """Göreli bir URL'i sitenin kök adresine göre mutlak hale getirir."""
    return urljoin(BASE_URL + "/", url.strip())


def format_minutes(total_minutes: int) -> str:
    """Dakika cinsinden süreyi okunabilir Türkçe metne çevirir (örn. 90 -> "1 saat 30 dakika")."""
    if total_minutes <= 0:
        return DEFAULT_VALUE
    hours, minutes = divmod(total_minutes, 60)
    parts: list[str] = []
    if hours:
        parts.append(f"{hours} saat")
    if minutes:
        parts.append(f"{minutes} dakika")
    return " ".join(parts)


def parse_iso_duration(value: Optional[str]) -> int:
    """ISO 8601 süresini ("PT1H20M") dakikaya çevirir. Çözülemezse 0 döner."""
    if not value:
        return 0
    match = _ISO_DURATION_RE.match(value.strip())
    if not match:
        return 0
    parts = {k: int(v) if v else 0 for k, v in match.groupdict().items()}
    total = parts["days"] * 1440 + parts["hours"] * 60 + parts["minutes"]
    if parts["seconds"] >= 30:
        total += 1
    return total


def parse_duration_text(text: Optional[str]) -> int:
    """"15dk Hazırlık, 25dk Pişirme" ya da "1 saat 10 dk" gibi metinlerdeki süreleri toplar."""
    if not text:
        return 0
    minutes = sum(int(m.group(1)) for m in _MINUTES_TEXT_RE.finditer(text))
    hours = sum(int(h.group(1)) for h in _HOURS_TEXT_RE.finditer(text))
    return hours * 60 + minutes


def normalize_servings(value: Optional[str]) -> str:
    """Porsiyon bilgisini "4 kişilik" / "2-4 kişilik" biçimine getirir."""
    text = clean_text(value)
    if not text:
        return DEFAULT_VALUE
    match = re.search(r"\d+\s*(?:-|–)\s*\d+|\d+", text)
    if not match:
        return text
    number = re.sub(r"\s*[-–]\s*", "-", match.group(0))
    return f"{number} kişilik"
