"""
Malzeme satırlarından standart malzeme adlarını (etiket) çıkarır.

Örnek:
    "1 su bardağı kırmızı mercimek"      -> ["mercimek"]
    "2 yemek kaşığı biber salçası"       -> ["biber salçası"]
    "1 yemek kaşığı tereyağı veya margarin" -> ["tereyağı"]

Frontend'deki "dolabımda ne var?" özelliği bu etiketleri kullanır: kullanıcının
seçtiği malzemelerle tarifin etiketleri karşılaştırılır.

Yeni bir malzeme tanıtmak için INGREDIENT_CATALOG'a satır eklemeniz yeterlidir.
Ardından `python main.py --retag` ile siteye yeniden istek atmadan mevcut
recipes.json dosyası güncellenir.
"""

from __future__ import annotations

import re
import unicodedata
from typing import NamedTuple


class IngredientInfo(NamedTuple):
    """Katalogdaki bir malzemenin bilgileri."""

    name: str          # Standart ad (JSON'a yazılan etiket)
    group: str         # Arayüzde gruplama için
    staple: bool       # Çoğu evde bulunan temel malzeme mi (tuz, su, baharat...)


# Grup adları arayüzde bu sırayla gösterilir.
GROUPS: tuple[str, ...] = (
    "sebze",
    "meyve",
    "et, tavuk, balık",
    "süt ürünleri ve yumurta",
    "bakliyat ve tahıl",
    "kiler",
    "baharat",
)

# (standart ad, grup, temel mi, [arama kalıpları])
# Kalıplar kelime başına bağlıdır, ek alabilir: "soğan" -> "soğanı", "soğanlar" da eşleşir.
# Uzun kalıplar önce denenir; "biber salçası", "biber"den önce yakalanır.
_CATALOG_ROWS: list[tuple[str, str, bool, list[str]]] = [
    # --- sebze ---
    ("soğan", "sebze", False, ["kuru soğan", "soğan", "arpacık soğan", "mor soğan"]),
    ("yeşil soğan", "sebze", False, ["yeşil soğan", "taze soğan"]),
    ("sarımsak", "sebze", False, ["sarımsak"]),
    ("domates", "sebze", False, ["domates", "çeri domates", "kiraz domates"]),
    ("biber", "sebze", False, ["yeşil biber", "sivri biber", "çarliston biber", "kapya biber",
                                "dolmalık biber", "kırmızı biber", "köz biber", "kapya", "biber"]),
    ("patates", "sebze", False, ["patates"]),
    ("havuç", "sebze", False, ["havuç"]),
    ("patlıcan", "sebze", False, ["patlıcan"]),
    ("kabak", "sebze", False, ["kabak"]),
    ("ıspanak", "sebze", False, ["ıspanak"]),
    ("maydanoz", "sebze", False, ["maydanoz"]),
    ("dereotu", "sebze", False, ["dereotu", "dere otu"]),
    ("taze nane", "sebze", False, ["taze nane"]),
    ("marul", "sebze", False, ["marul", "kıvırcık", "göbek salata", "roka", "yeşillik"]),
    ("salatalık", "sebze", False, ["salatalık", "hıyar", "kornişon"]),
    ("mantar", "sebze", False, ["mantar"]),
    ("brokoli", "sebze", False, ["brokoli"]),
    ("karnabahar", "sebze", False, ["karnabahar"]),
    ("lahana", "sebze", False, ["lahana"]),
    ("pırasa", "sebze", False, ["pırasa"]),
    ("kereviz", "sebze", False, ["kereviz"]),
    ("bezelye", "sebze", False, ["bezelye", "garnitür"]),
    ("taze fasulye", "sebze", False, ["taze fasulye"]),
    ("bamya", "sebze", False, ["bamya"]),
    ("mısır", "sebze", False, ["konserve mısır", "mısır tanesi", "haşlanmış mısır", "mısır"]),
    ("zencefil", "sebze", False, ["zencefil"]),
    ("pancar", "sebze", False, ["pancar"]),
    ("turp", "sebze", False, ["turp"]),
    ("asma yaprağı", "sebze", False, ["asma yaprağı", "yaprak sarma", "dolmalık yaprak"]),
    ("zeytin", "sebze", False, ["zeytin"]),
    ("kapari", "sebze", False, ["kapari"]),
    ("fesleğen", "sebze", False, ["fesleğen"]),
    ("semizotu", "sebze", False, ["semizotu", "semiz otu"]),
    ("tatlı patates", "sebze", False, ["tatlı patates"]),
    ("balkabağı", "sebze", False, ["balkabağı", "bal kabağı"]),

    # --- meyve ---
    ("limon", "meyve", False, ["limon"]),
    ("portakal", "meyve", False, ["portakal"]),
    ("elma", "meyve", False, ["elma"]),
    ("muz", "meyve", False, ["muz"]),
    ("çilek", "meyve", False, ["çilek"]),
    ("vişne", "meyve", False, ["vişne"]),
    ("nar", "meyve", False, ["nar ekşisi", "nar taneleri", "nar"]),
    ("kuru üzüm", "meyve", False, ["kuru üzüm", "kuş üzümü", "üzüm"]),
    ("kayısı", "meyve", False, ["kayısı"]),
    ("hurma", "meyve", False, ["hurma"]),
    ("şeftali", "meyve", False, ["şeftali", "nektarin"]),
    ("avokado", "meyve", False, ["avokado"]),
    ("hindistan cevizi", "meyve", False, ["hindistan cevizi"]),

    # --- et, tavuk, balık ---
    ("kıyma", "et, tavuk, balık", False, ["kıyma"]),
    ("dana eti", "et, tavuk, balık", False, ["kuşbaşı", "dana eti", "dana", "biftek", "bonfile",
                                             "antrikot", "kavurma", "et"]),
    ("kuzu eti", "et, tavuk, balık", False, ["kuzu"]),
    ("tavuk", "et, tavuk, balık", False, ["tavuk göğüs eti", "tavuk but eti", "tavuk eti", "tavuk", "piliç", "baget", "kanat"]),
    ("hindi", "et, tavuk, balık", False, ["hindi"]),
    ("balık", "et, tavuk, balık", False, ["balık", "somon", "levrek", "çupra", "hamsi", "ton balığı"]),
    ("karides", "et, tavuk, balık", False, ["karides"]),
    ("sucuk", "et, tavuk, balık", False, ["sucuk"]),
    ("sosis", "et, tavuk, balık", False, ["sosis"]),
    ("pastırma", "et, tavuk, balık", False, ["pastırma"]),
    ("salam", "et, tavuk, balık", False, ["salam", "jambon"]),

    # --- süt ürünleri ve yumurta ---
    ("yumurta", "süt ürünleri ve yumurta", False, ["yumurta"]),
    ("süt", "süt ürünleri ve yumurta", False, ["süt"]),
    ("yoğurt", "süt ürünleri ve yumurta", False, ["süzme yoğurt", "yoğurt"]),
    ("tereyağı", "süt ürünleri ve yumurta", False, ["tereyağı", "tereyağ", "margarin"]),
    ("krema", "süt ürünleri ve yumurta", False, ["krema", "sıvı krema", "krem şanti"]),
    ("beyaz peynir", "süt ürünleri ve yumurta", False, ["beyaz peynir", "tulum peyniri", "lor", "feta"]),
    ("kaşar peyniri", "süt ürünleri ve yumurta", False, ["kaşar", "mozzarella", "çedar", "cheddar",
                                                         "rendelenmiş peynir", "parmesan", "peynir rendesi"]),
    ("krem peynir", "süt ürünleri ve yumurta", False, ["krem peynir", "labne", "mascarpone"]),
    ("kaymak", "süt ürünleri ve yumurta", False, ["kaymak"]),

    # --- bakliyat ve tahıl ---
    ("mercimek", "bakliyat ve tahıl", False, ["kırmızı mercimek", "yeşil mercimek", "sarı mercimek", "mercimek"]),
    ("nohut", "bakliyat ve tahıl", False, ["nohut"]),
    ("kuru fasulye", "bakliyat ve tahıl", False, ["kuru fasulye", "barbunya", "fasulye"]),
    ("pirinç", "bakliyat ve tahıl", False, ["pirinç", "baldo", "osmancık"]),
    ("bulgur", "bakliyat ve tahıl", False, ["köftelik bulgur", "pilavlık bulgur", "bulgur"]),
    ("şehriye", "bakliyat ve tahıl", False, ["arpa şehriye", "tel şehriye", "şehriye"]),
    ("makarna", "bakliyat ve tahıl", False, ["makarna", "spagetti", "penne", "fiyonk", "burgu", "erişte", "lazanya", "kuskus"]),
    ("un", "bakliyat ve tahıl", False, ["un"]),
    ("irmik", "bakliyat ve tahıl", False, ["irmik"]),
    ("mısır unu", "bakliyat ve tahıl", False, ["mısır unu"]),
    ("nişasta", "bakliyat ve tahıl", False, ["mısır nişastası", "buğday nişastası", "nişasta"]),
    ("yulaf", "bakliyat ve tahıl", False, ["yulaf"]),
    ("buğday", "bakliyat ve tahıl", False, ["aşurelik buğday", "buğday", "yarma"]),
    ("tarhana", "bakliyat ve tahıl", False, ["tarhana"]),
    ("galeta unu", "bakliyat ve tahıl", False, ["galeta unu", "galeta"]),
    ("ekmek", "bakliyat ve tahıl", False, ["bayat ekmek", "ekmek içi", "ekmek", "etimek", "bazlama", "lavaş", "tortilla"]),
    ("yufka", "bakliyat ve tahıl", False, ["yufka"]),
    ("milföy", "bakliyat ve tahıl", False, ["milföy"]),
    ("kadayıf", "bakliyat ve tahıl", False, ["kadayıf"]),
    ("bisküvi", "bakliyat ve tahıl", False, ["bisküvi", "kraker"]),

    # --- kiler ---
    ("domates salçası", "kiler", False, ["domates salçası", "salça"]),
    ("biber salçası", "kiler", False, ["biber salçası", "acı biber salçası", "tatlı biber salçası"]),
    ("toz şeker", "kiler", False, ["toz şeker", "pudra şekeri", "esmer şeker", "şeker"]),
    ("bal", "kiler", False, ["bal"]),
    ("pekmez", "kiler", False, ["pekmez"]),
    ("kabartma tozu", "kiler", False, ["kabartma tozu"]),
    ("karbonat", "kiler", False, ["karbonat"]),
    ("maya", "kiler", False, ["instant maya", "kuru maya", "yaş maya", "maya"]),
    ("vanilin", "kiler", False, ["vanilin", "vanilya"]),
    ("kakao", "kiler", False, ["kakao"]),
    ("çikolata", "kiler", False, ["bitter çikolata", "sütlü çikolata", "beyaz çikolata", "damla çikolata", "çikolata"]),
    ("fındık", "kiler", False, ["fındık"]),
    ("ceviz", "kiler", False, ["ceviz"]),
    ("fıstık", "kiler", False, ["antep fıstığı", "fıstık ezmesi", "fıstık"]),
    ("badem", "kiler", False, ["badem"]),
    ("susam", "kiler", False, ["susam", "çörek otu"]),
    ("tahin", "kiler", False, ["tahin"]),
    ("zeytinyağı", "kiler", False, ["zeytinyağı", "zeytin yağı", "sızma"]),
    ("sirke", "kiler", False, ["sirke"]),
    ("mayonez", "kiler", False, ["mayonez"]),
    ("ketçap", "kiler", False, ["ketçap"]),
    ("hardal", "kiler", False, ["hardal"]),
    ("soya sosu", "kiler", False, ["soya sosu"]),
    ("et suyu", "kiler", False, ["et suyu", "tavuk suyu", "kemik suyu", "sebze suyu", "tavuk bulyonu"]),
    ("hazır çorba", "kiler", False, ["tavuk bulyon", "et bulyon", "sebze bulyon", "bulyon", "hazır çorba"]),
    ("konserve domates", "kiler", False, ["konserve domates", "domates püresi", "rendelenmiş domates"]),
    ("jelatin", "kiler", False, ["jelatin"]),
    ("hindistan cevizi rendesi", "kiler", False, ["hindistan cevizi rendesi"]),

    # --- baharat (çoğu evde bulunur, varsayılan olarak "evde var" sayılır) ---
    ("tuz", "baharat", True, ["tuz"]),
    ("su", "baharat", True, ["sıcak su", "soğuk su", "ılık su", "kaynar su", "su"]),
    ("sıvı yağ", "baharat", True, ["ayçiçek yağı", "sıvı yağ", "sıvıyağ", "kızartma yağı", "yağ"]),
    ("karabiber", "baharat", True, ["karabiber", "kara biber"]),
    ("pul biber", "baharat", True, ["pul biber", "pulbiber", "kırmızı pul biber", "isot", "acı pul biber"]),
    ("toz biber", "baharat", True, ["toz kırmızı biber", "kırmızı toz biber", "toz biber", "tozbiber", "paprika"]),
    ("kimyon", "baharat", True, ["kimyon"]),
    ("nane", "baharat", True, ["kuru nane", "nane"]),
    ("kekik", "baharat", True, ["kekik"]),
    ("sumak", "baharat", True, ["sumak"]),
    ("yenibahar", "baharat", True, ["yenibahar", "yeni bahar"]),
    ("tarçın", "baharat", True, ["tarçın"]),
    ("defne yaprağı", "baharat", True, ["defne"]),
    ("zerdeçal", "baharat", True, ["zerdeçal", "köri"]),
    ("karanfil", "baharat", True, ["karanfil"]),
    ("baharat", "baharat", True, ["baharat", "köfte baharatı", "çemen"]),
]

# Ölçü birimleri: "su bardağı" içindeki "su"nun malzeme sanılmaması için önce silinir.
_MEASURE_PATTERNS: tuple[str, ...] = (
    "su bardağı", "çay bardağı", "kahve fincanı", "yemek kaşığı", "tatlı kaşığı",
    "çay kaşığı", "kahve kaşığı", "silme", "tepeleme", "yarım", "çeyrek", "buçuk",
    "adet", "paket", "kutu", "demet", "tutam", "avuç", "dilim", "diş", "tane",
    "yaprak", "dal", "parmak", "orta boy", "büyük boy", "küçük boy", "kg", "gram", "gr", "ml", "litre", "lt",
    "kase", "kepçe", "fincan", "bardak", "kaşık",
    # Malzeme sanılabilecek niteleyiciler ("orta yağlı kıyma" -> "yağ" değil)
    "az yağlı", "tam yağlı", "yağlı", "yağsız", "sulu", "susuz", "unlu", "şekerli", "şekersiz", "tuzlu", "tuzsuz",
)

# "A veya B" satırlarında sadece ilk seçenek zorunlu malzeme sayılır.
_TR_LETTERS = "a-zçğıöşüâîû"
# "/" sadece iki kelime arasındaysa ayraçtır; "1/2" gibi kesirlerde değil.
_ALTERNATIVE_RE = re.compile(rf"\s(?:veya|ya da|yahut)\s|(?<=[{_TR_LETTERS}])\s*/\s*(?=[{_TR_LETTERS}])")

_WORD_END_RE = re.compile(rf"[{_TR_LETTERS}]*")

INGREDIENT_CATALOG: dict[str, IngredientInfo] = {
    name: IngredientInfo(name, group, staple) for name, group, staple, _ in _CATALOG_ROWS
}

# (kalıp, standart ad) çiftleri, uzundan kısaya sıralı.
_PATTERNS: list[tuple[re.Pattern[str], str]] = sorted(
    (
        (re.compile(rf"(?<![{_TR_LETTERS}]){re.escape(pattern)}"), name)
        for name, _, _, patterns in _CATALOG_ROWS
        for pattern in patterns
    ),
    key=lambda item: -len(item[0].pattern),
)
_MEASURE_RE = re.compile(
    rf"(?<![{_TR_LETTERS}])(?:{'|'.join(re.escape(m) for m in sorted(_MEASURE_PATTERNS, key=len, reverse=True))})[{_TR_LETTERS}]*"
)


def turkish_lower(text: str) -> str:
    """Türkçe kurallarına uygun küçük harfe çevirir (I -> ı, İ -> i)."""
    # NFC: "c" + birleştirici çengel gibi ayrık yazılmış harfleri tek karaktere indirir.
    text = unicodedata.normalize("NFC", text)
    return text.replace("I", "ı").replace("İ", "i").lower().replace("i̇", "i")


def extract_tags(line: str) -> list[str]:
    """Tek bir malzeme satırındaki standart malzeme adlarını döndürür.

    "A veya B" satırlarında malzeme içeren ilk seçenek kullanılır
    ("haşlanmış ya da konserve bezelye" -> ilk parçada malzeme yok -> "bezelye").
    """
    text = turkish_lower(line)
    text = re.sub(r"\([^)]*\)", " ", text)                  # parantez içi açıklamalar
    pieces = _ALTERNATIVE_RE.split(text)
    for i, piece in enumerate(pieces):
        # Son parçaya kadar gelindiyse kalan her şey birlikte değerlendirilir.
        candidate = " ".join(pieces[i:]) if i == len(pieces) - 1 else piece
        found = _match_catalog(candidate)
        if found:
            return found
    return []


def _match_catalog(text: str) -> list[str]:
    text = _MEASURE_RE.sub(" ", text)
    text = re.sub(r"[\d.,/½¼¾-]+", " ", text)
    found: list[str] = []
    for regex, name in _PATTERNS:
        match = regex.search(text)
        if match:
            if name not in found:
                found.append(name)
            # Eşleşen kelimeyi ekiyle birlikte boşlukla değiştir: "biber salçası" bulunduysa
            # "biber" ayrıca sayılmasın, "limonun" içindeki "-un" eki "un" sanılmasın.
            end = _WORD_END_RE.match(text, match.end()).end()
            text = text[: match.start()] + " " * (end - match.start()) + text[end:]
    return found


def extract_ingredient_tags(ingredients: list[str]) -> list[str]:
    """Bir tarifin tüm malzeme satırlarından tekil, sıralı etiket listesi üretir."""
    tags: list[str] = []
    for line in ingredients:
        for tag in extract_tags(line):
            if tag not in tags:
                tags.append(tag)
    return tags
