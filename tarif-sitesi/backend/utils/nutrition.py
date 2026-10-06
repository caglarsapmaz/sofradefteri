"""
Tarif başına TAHMİNİ besin değeri hesaplama.

Kaynak site kalori/makro bilgisi vermediği için değerler malzeme listesinden
tahmin edilir:

    "1 su bardağı un"  -> miktar 1, birim "su bardağı" (200 ml) x un yoğunluğu (0,55 g/ml) = 110 g
    110 g un           -> 100 g başına 364 kcal, 10 g protein ... tablosuyla çarpılır
    tarif toplamı      -> porsiyon sayısına ("4-6 kişilik" -> 5) bölünür

Değerler yaklaşık 100 g başına ortalamalardır (USDA / TürKomp ölçeğinde
yuvarlanmış). Ölçüler ev ölçüsü olduğu için sonuç ±%20-30 sapabilir; bu yüzden
JSON'da "estimated": true ve bir "confidence" (güven) oranı yazılır.

Yeni bir malzeme kataloğa eklendiğinde (utils/ingredients.py) buraya da
besin değeri eklenmelidir; eklenmezse o malzeme hesaba katılmaz ve güven düşer.
"""

from __future__ import annotations

import re
import unicodedata
from typing import NamedTuple, Optional

from utils.ingredients import INGREDIENT_CATALOG, extract_tags, turkish_lower


class Food(NamedTuple):
    """100 g başına besin değeri ve ölçü dönüşümleri."""

    kcal: float
    protein: float
    carbs: float
    fat: float
    density: float = 1.0        # g/ml — su bardağı, kaşık gibi hacim ölçüleri için
    piece: float = 50.0         # 1 adet / tane kaç gram
    package: float = 250.0      # 1 paket kaç gram
    default: float = 20.0       # miktar yazmıyorsa varsayılan gram ("Maydanoz", "Ceviz")


# Standart malzeme adı -> 100 g başına değerler
FOODS: dict[str, Food] = {
    # sebze
    "soğan": Food(40, 1.1, 9.3, 0.1, 0.6, 110, default=50),
    "yeşil soğan": Food(32, 1.8, 7.3, 0.2, 0.3, 15, default=20),
    "sarımsak": Food(149, 6.4, 33, 0.5, 0.6, 5, default=5),
    "domates": Food(18, 0.9, 3.9, 0.2, 0.9, 120, default=60),
    "biber": Food(20, 0.9, 4.6, 0.2, 0.5, 50, default=30),
    "patates": Food(77, 2, 17, 0.1, 0.65, 170, default=150),
    "havuç": Food(41, 0.9, 10, 0.2, 0.55, 70, default=50),
    "patlıcan": Food(25, 1, 6, 0.2, 0.4, 250),
    "kabak": Food(17, 1.2, 3.1, 0.3, 0.5, 200),
    "ıspanak": Food(23, 2.9, 3.6, 0.4, 0.25, 30, 500),
    "maydanoz": Food(36, 3, 6.3, 0.8, 0.25, 50, default=10),
    "dereotu": Food(43, 3.5, 7, 1.1, 0.25, 50, default=10),
    "taze nane": Food(44, 3.3, 8.4, 0.7, 0.25, 30, default=5),
    "marul": Food(15, 1.4, 2.9, 0.2, 0.25, 300, default=50),
    "salatalık": Food(15, 0.7, 3.6, 0.1, 0.6, 150, default=50),
    "mantar": Food(22, 3.1, 3.3, 0.3, 0.4, 18, 250),
    "brokoli": Food(34, 2.8, 7, 0.4, 0.4, 400),
    "karnabahar": Food(25, 1.9, 5, 0.3, 0.4, 600),
    "lahana": Food(25, 1.3, 5.8, 0.1, 0.35, 1000),
    "pırasa": Food(61, 1.5, 14, 0.3, 0.4, 150),
    "kereviz": Food(42, 1.5, 9.2, 0.3, 0.5, 400),
    "bezelye": Food(81, 5.4, 14, 0.4, 0.65, 5, 400),
    "taze fasulye": Food(31, 1.8, 7, 0.2, 0.45, 8),
    "bamya": Food(33, 1.9, 7, 0.2, 0.45, 10),
    "mısır": Food(86, 3.3, 19, 1.4, 0.7, 150, 220),
    "zencefil": Food(80, 1.8, 18, 0.8, 0.6, 20, default=5),
    "pancar": Food(43, 1.6, 10, 0.2, 0.6, 150),
    "turp": Food(16, 0.7, 3.4, 0.1, 0.6, 100),
    "asma yaprağı": Food(93, 5.6, 17, 2.1, 0.3, 3, 250),
    "zeytin": Food(115, 0.8, 6, 11, 0.6, 4, default=20),
    "kapari": Food(23, 2.4, 4.9, 0.9, 0.6, 1, default=10),
    "fesleğen": Food(23, 3.2, 2.7, 0.6, 0.2, 1, default=5),
    "semizotu": Food(20, 2, 3.4, 0.4, 0.25, 150, default=150),
    "tatlı patates": Food(86, 1.6, 20, 0.1, 0.65, 200),
    "balkabağı": Food(26, 1, 6.5, 0.1, 0.5, 1000),
    # meyve
    "limon": Food(29, 1.1, 9.3, 0.3, 1.0, 100, default=15),
    "portakal": Food(47, 0.9, 12, 0.1, 1.0, 180),
    "elma": Food(52, 0.3, 14, 0.2, 0.6, 180),
    "muz": Food(89, 1.1, 23, 0.3, 0.6, 120),
    "çilek": Food(32, 0.7, 7.7, 0.3, 0.6, 12),
    "vişne": Food(50, 1, 12, 0.3, 0.65, 5),
    "nar": Food(83, 1.7, 19, 1.2, 0.8, 250, default=20),
    "kuru üzüm": Food(299, 3.1, 79, 0.5, 0.6, 1, 200),
    "kayısı": Food(48, 1.4, 11, 0.4, 0.6, 35),
    "hurma": Food(282, 2.5, 75, 0.4, 0.6, 8),
    "şeftali": Food(39, 0.9, 9.5, 0.3, 0.6, 150),
    "avokado": Food(160, 2, 8.5, 14.7, 0.6, 170),
    "hindistan cevizi": Food(354, 3.3, 15, 33, 0.35, 400, 100),
    # et, tavuk, balık
    "kıyma": Food(250, 17, 0, 20, 0.9, 100, 500, default=250),
    "dana eti": Food(200, 26, 0, 10, 0.9, 150, 500, default=250),
    "kuzu eti": Food(250, 25, 0, 16, 0.9, 200, 500, default=250),
    "tavuk": Food(175, 28, 0, 6, 0.9, 150, 500, default=250),
    "hindi": Food(150, 29, 0, 3, 0.9, 150, 500, default=250),
    "balık": Food(180, 22, 0, 10, 0.9, 300, 500, default=250),
    "karides": Food(99, 24, 0.2, 0.3, 0.9, 15, 250),
    "sucuk": Food(450, 20, 2, 40, 0.9, 10, 250),
    "sosis": Food(300, 12, 3, 27, 0.9, 50, 250),
    "pastırma": Food(250, 30, 1, 14, 0.9, 10, 100),
    "salam": Food(300, 15, 2, 26, 0.9, 10, 100),
    # süt ürünleri ve yumurta
    "yumurta": Food(143, 12.6, 0.7, 9.5, 1.0, 55, default=55),
    "süt": Food(61, 3.2, 4.8, 3.3, 1.03, 200, 1000),
    "yoğurt": Food(63, 3.5, 4.7, 3.3, 1.03, 200, 1000, default=100),
    "tereyağı": Food(717, 0.9, 0.1, 81, 0.95, 10, 250, default=15),
    "krema": Food(340, 2, 3, 36, 1.0, 200, 200),
    "beyaz peynir": Food(264, 17, 1.5, 21, 0.5, 30, 500, default=50),
    "kaşar peyniri": Food(350, 25, 2, 27, 0.45, 20, 250, default=50),
    "krem peynir": Food(340, 6, 4, 34, 1.0, 200, 200),
    "kaymak": Food(500, 3, 3, 52, 1.0, 100, 200),
    # bakliyat ve tahıl
    "mercimek": Food(350, 24, 60, 1.5, 0.85, 1, 1000),
    "nohut": Food(364, 19, 61, 6, 0.8, 1, 1000),
    "kuru fasulye": Food(333, 23, 60, 0.8, 0.8, 1, 1000),
    "pirinç": Food(360, 7, 79, 0.6, 0.9, 1, 1000),
    "bulgur": Food(342, 12, 76, 1.3, 0.85, 1, 1000),
    "şehriye": Food(371, 13, 75, 1.5, 0.6, 1, 500),
    "makarna": Food(371, 13, 75, 1.5, 0.45, 1, 500),
    "un": Food(364, 10, 76, 1, 0.55, 1, 1000, default=30),
    "irmik": Food(360, 12.7, 73, 1, 0.8, 1, 500),
    "mısır unu": Food(365, 7, 77, 3.9, 0.6, 1, 500),
    "nişasta": Food(381, 0.3, 91, 0.1, 0.6, 1, 200),
    "yulaf": Food(389, 17, 66, 7, 0.45, 1, 500),
    "buğday": Food(340, 13, 72, 2.5, 0.8, 1, 1000),
    "tarhana": Food(350, 13, 65, 4, 0.7, 1, 500),
    "galeta unu": Food(395, 13, 72, 5, 0.5, 1, 200, default=30),
    "ekmek": Food(265, 9, 49, 3.2, 0.3, 60, 400, default=60),
    "yufka": Food(300, 9, 60, 2.5, 1.0, 120, 500),
    "milföy": Food(550, 6, 45, 38, 1.0, 70, 700),
    "kadayıf": Food(360, 9, 75, 2, 0.3, 1, 500),
    "bisküvi": Food(450, 7, 70, 16, 0.5, 8, 150),
    # kiler
    "domates salçası": Food(82, 4.3, 19, 0.5, 1.1, 20, 830, default=15),
    "biber salçası": Food(90, 3, 18, 1, 1.1, 20, 830, default=15),
    "toz şeker": Food(387, 0, 100, 0, 0.85, 5, 1000, default=10),
    "bal": Food(304, 0.3, 82, 0, 1.4, 20, 450, default=15),
    "pekmez": Food(290, 0, 72, 0, 1.4, 20, 700, default=15),
    "kabartma tozu": Food(53, 0, 28, 0, 0.9, 10, 10, default=5),
    "karbonat": Food(0, 0, 0, 0, 1.0, 5, 10, default=2),
    "maya": Food(325, 40, 41, 7.6, 0.6, 10, 10, default=5),
    "vanilin": Food(0, 0, 0, 0, 1.0, 5, 5, default=1),
    "kakao": Food(228, 20, 58, 14, 0.45, 5, 100, default=10),
    "çikolata": Food(546, 5, 60, 31, 0.6, 80, 80, default=20),
    "fındık": Food(628, 15, 17, 61, 0.55, 1, 200, default=20),
    "ceviz": Food(654, 15, 14, 65, 0.45, 5, 200, default=20),
    "fıstık": Food(560, 20, 28, 45, 0.55, 1, 200, default=15),
    "badem": Food(579, 21, 22, 50, 0.55, 1, 200, default=15),
    "susam": Food(573, 18, 23, 50, 0.6, 1, 100, default=5),
    "tahin": Food(595, 17, 21, 54, 1.0, 20, 300, default=15),
    "zeytinyağı": Food(884, 0, 0, 100, 0.91, 10, 1000, default=15),
    "sirke": Food(18, 0, 0.04, 0, 1.0, 10, 500, default=10),
    "mayonez": Food(680, 1, 0.6, 75, 0.95, 15, 250, default=15),
    "ketçap": Food(101, 1, 27, 0.1, 1.1, 15, 400, default=15),
    "hardal": Food(66, 4, 6, 4, 1.0, 10, 200, default=5),
    "soya sosu": Food(53, 8, 5, 0, 1.1, 10, 250, default=10),
    "et suyu": Food(15, 2, 0.5, 0.5, 1.0, 200, 1000, default=200),
    "hazır çorba": Food(250, 10, 40, 7, 0.8, 10, 70, default=10),
    "konserve domates": Food(32, 1.6, 7, 0.2, 1.0, 120, 400, default=100),
    "jelatin": Food(335, 86, 0, 0, 0.7, 10, 10),
    "hindistan cevizi rendesi": Food(660, 7, 24, 65, 0.35, 1, 100, default=10),
    # temel malzemeler: tuz, su ve baharatların kalorisi ihmal edilir, yağ hesaba katılır
    "sıvı yağ": Food(884, 0, 0, 100, 0.92, 10, 1000, default=20),
    "tuz": Food(0, 0, 0, 0, default=0),
    "su": Food(0, 0, 0, 0, default=0),
    "karabiber": Food(0, 0, 0, 0, default=0),
    "pul biber": Food(0, 0, 0, 0, default=0),
    "toz biber": Food(0, 0, 0, 0, default=0),
    "kimyon": Food(0, 0, 0, 0, default=0),
    "nane": Food(0, 0, 0, 0, default=0),
    "kekik": Food(0, 0, 0, 0, default=0),
    "sumak": Food(0, 0, 0, 0, default=0),
    "yenibahar": Food(0, 0, 0, 0, default=0),
    "tarçın": Food(0, 0, 0, 0, default=0),
    "defne yaprağı": Food(0, 0, 0, 0, default=0),
    "zerdeçal": Food(0, 0, 0, 0, default=0),
    "karanfil": Food(0, 0, 0, 0, default=0),
    "baharat": Food(0, 0, 0, 0, default=0),
}

# Hacim ölçüleri (ml)
_VOLUME_UNITS: dict[str, float] = {
    "su bardağı": 200, "çay bardağı": 100, "kahve fincanı": 70, "fincan": 70, "bardak": 200,
    "yemek kaşığı": 15, "tatlı kaşığı": 7, "çay kaşığı": 3, "kahve kaşığı": 2, "kaşık": 15,
    "kase": 250, "kepçe": 100,
}
# Kütle / sıvı birimleri
_MASS_UNITS: dict[str, float] = {"kg": 1000, "kilo": 1000, "gram": 1, "gr": 1, "g": 1}
_LIQUID_UNITS: dict[str, float] = {"litre": 1000, "lt": 1000, "l": 1000, "ml": 1, "cc": 1}
# Sabit ağırlıklı ev ölçüleri (gram)
_FIXED_UNITS: dict[str, float] = {"tutam": 1, "avuç": 30, "dilim": 25, "dal": 10, "demet": 50, "yaprak": 3}
# Yumurtanın sadece bir kısmı kullanılıyorsa adet ağırlığı çarpanı
_EGG_PART: dict[str, float] = {"sarısı": 0.33, "akı": 0.6}
# Porsiyon başına bundan fazla kalori çıkıyorsa sitedeki kişi sayısı gerçekçi değildir
# (ör. 3,5 kg'lık içli köfte için "1-2 kişilik"); porsiyon REFERENCE_PORTION_KCAL'a göre yeniden ölçeklenir.
MAX_PORTION_KCAL = 1200
REFERENCE_PORTION_KCAL = 600
_SIZE_FACTOR: dict[str, float] = {"büyük boy": 1.4, "iri": 1.4, "büyük": 1.4, "küçük boy": 0.7, "küçük": 0.7}

_TR = "a-zçğıöşüâîû"
_NUMBER_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:-|–|ile)\s*(\d+(?:[.,]\d+)?)|(\d+)\s*/\s*(\d+)|(\d+(?:[.,]\d+)?)")
_WORD_NUMBERS: dict[str, float] = {"yarım": 0.5, "çeyrek": 0.25, "bir": 1, "iki": 2, "üç": 3, "dört": 4, "beş": 5}
_FRACTIONS: dict[str, float] = {"½": 0.5, "¼": 0.25, "¾": 0.75, "⅓": 1 / 3}


def _to_float(text: str) -> float:
    return float(text.replace(",", "."))


def parse_amount(line: str) -> Optional[float]:
    """Satırdaki sayısal miktarı döndürür: "2-3" -> 2.5, "1/2" -> 0.5, "1 buçuk" -> 1.5, "yarım" -> 0.5."""
    text = turkish_lower(line)
    text = re.sub(r"\([^)]*\)", " ", text)
    for sym, val in _FRACTIONS.items():
        text = text.replace(sym, f" {val} ")
    value: Optional[float] = None
    match = _NUMBER_RE.search(text)
    if match:
        if match.group(1):
            value = (_to_float(match.group(1)) + _to_float(match.group(2))) / 2
        elif match.group(3):
            value = int(match.group(3)) / max(1, int(match.group(4)))
        else:
            value = _to_float(match.group(5))
    else:
        for word, val in _WORD_NUMBERS.items():
            if re.search(rf"(?<![{_TR}]){word}(?![{_TR}])", text):
                value = val
                break
    if value is not None and re.search(rf"(?<![{_TR}])buçuk", text):
        value += 0.5
    return value


def line_grams(line: str, food: Food) -> tuple[float, bool]:
    """Bir malzeme satırının gram karşılığını tahmin eder.

    Dönüş: (gram, miktar_satırdan_okundu_mu)
    Miktar parantez dışında yoksa parantez içine bakılır:
    "Aldığı kadar un (yaklaşık 2.5-3 su bardağı)" -> 2.75 su bardağı.
    """
    grams, found = _line_grams(line, food)
    if not found:
        inner = " ".join(re.findall(r"\(([^)]*)\)", line))
        if inner and parse_amount(inner) is not None:
            grams, found = _line_grams(inner, food)
            if not found:
                grams = food.default
    return grams, found


def _line_grams(line: str, food: Food) -> tuple[float, bool]:
    text = turkish_lower(unicodedata.normalize("NFC", line))
    text = re.sub(r"\([^)]*\)", " ", text)
    amount = parse_amount(line)

    # 400g, 1 kg, 500 ml gibi doğrudan ölçüler
    direct = re.search(rf"(\d+(?:[.,]\d+)?)\s*(kg|kilo|gram|gr|g|litre|lt|ml|cc|l)(?![{_TR}])", text)
    if direct:
        qty, unit = _to_float(direct.group(1)), direct.group(2)
        if unit in _MASS_UNITS:
            return qty * _MASS_UNITS[unit], True
        return qty * _LIQUID_UNITS[unit] * food.density, True

    for unit, ml in sorted(_VOLUME_UNITS.items(), key=lambda kv: -len(kv[0])):
        if re.search(rf"(?<![{_TR}]){unit}", text):
            return (amount or 1) * ml * food.density, True

    if re.search(rf"(?<![{_TR}])paket", text):
        return (amount or 1) * food.package, True
    if re.search(rf"(?<![{_TR}])kutu", text):
        return (amount or 1) * max(food.package, 400), True
    if re.search(rf"(?<![{_TR}])diş", text):
        return (amount or 1) * 5, True
    for unit, grams in _FIXED_UNITS.items():
        if re.search(rf"(?<![{_TR}]){unit}", text):
            return (amount or 1) * grams, True

    if amount is not None:
        factor = next((f for word, f in _SIZE_FACTOR.items() if word in text), 1.0)
        factor *= next((f for word, f in _EGG_PART.items() if re.search(rf"(?<![{_TR}]){word}", text)), 1.0)
        return amount * food.piece * factor, True

    # "Kızartmak için sıvı yağ" gibi miktarsız satırlar
    return food.default, False


def parse_servings(servings: str) -> float:
    """"4-6 kişilik" -> 5, "16 kişilik" -> 16; bulunamazsa 4."""
    numbers = [int(n) for n in re.findall(r"\d+", servings or "")]
    if not numbers:
        return 4.0
    return sum(numbers[:2]) / len(numbers[:2])


def estimate_nutrition(ingredients: list[str], servings: str) -> dict[str, object]:
    """Tarifin porsiyon başına tahmini kalori ve makro değerlerini hesaplar."""
    total = {"kcal": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0}
    counted = quantified = 0

    for line in ingredients:
        tags = extract_tags(line)
        for position, tag in enumerate(tags):
            food = FOODS.get(tag)
            if food is None or food.kcal == 0 and food.default == 0:
                continue  # tuz, su, baharat: kalorisi ihmal edilir
            if position == 0:
                grams, from_line = line_grams(line, food)
            else:
                # Aynı satırdaki ikinci malzemenin miktarı yazmaz ("karabiber ve pul biber")
                grams, from_line = food.default, False
            grams = min(grams, 3000)
            factor = grams / 100
            total["kcal"] += food.kcal * factor
            total["protein"] += food.protein * factor
            total["carbs"] += food.carbs * factor
            total["fat"] += food.fat * factor
            if not INGREDIENT_CATALOG[tag].staple or tag == "sıvı yağ":
                counted += 1
                quantified += from_line

    portions = parse_servings(servings)
    adjusted = False
    if total["kcal"] / portions > MAX_PORTION_KCAL:
        portions = max(portions, round(total["kcal"] / REFERENCE_PORTION_KCAL))
        adjusted = True
    return {
        "calories": round(total["kcal"] / portions),
        "protein": round(total["protein"] / portions, 1),
        "carbs": round(total["carbs"] / portions, 1),
        "fat": round(total["fat"] / portions, 1),
        "servings_used": portions,
        "servings_adjusted": adjusted,
        "confidence": round(quantified / counted, 2) if counted else 0.0,
        "estimated": True,
    }
