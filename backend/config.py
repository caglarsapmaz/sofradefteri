"""
Proje ayarları.

Site yapısı değişirse SADECE bu dosyayı güncellemeniz yeterlidir:
- Kategori adresleri          -> CATEGORIES
- HTML seçicileri (selector)  -> SELECTORS
- Sayfalama biçimi            -> PAGINATION_PATTERN
- İstek ayarları              -> REQUEST_* sabitleri

Selector'lar 2026-10-06 tarihinde nefisyemektarifleri.com'un canlı sayfa
yapısı incelenerek doldurulmuştur.
"""

from pathlib import Path

# --------------------------------------------------------------------------- #
# Genel
# --------------------------------------------------------------------------- #
BASE_URL: str = "https://www.nefisyemektarifleri.com"
SOURCE_NAME: str = "nefisyemektarifleri.com"
ROBOTS_URL: str = f"{BASE_URL}/robots.txt"

BASE_DIR: Path = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR: Path = BASE_DIR / "output"
JSON_FILENAME: str = "recipes.json"
CSV_FILENAME: str = "recipes.csv"

# Veri bulunamadığında JSON'a yazılacak varsayılan değer (null yerine).
DEFAULT_VALUE: str = "Bilgi bulunamadı"

# Ödev şartı: en az bu kadar tarif çekilmeli.
DEFAULT_LIMIT: int = 15

# --------------------------------------------------------------------------- #
# HTTP istek ayarları
# --------------------------------------------------------------------------- #
REQUEST_TIMEOUT: int = 10          # saniye
REQUEST_DELAY: float = 1.5         # her istek arasında beklenecek süre (saniye)
MAX_RETRIES: int = 3               # başarısız istekte en fazla deneme sayısı
BACKOFF_BASE: float = 2.0          # bekleme = REQUEST_DELAY * BACKOFF_BASE ** (deneme - 1)
RETRY_STATUS_CODES: frozenset[int] = frozenset({429, 500, 502, 503, 504})

# robots.txt kontrolünde kullanılacak ajan adı. Site, adı belirtilmeyen
# tarayıcılar için "*" kurallarını uygular; biz de bu kurallara uyarız.
ROBOTS_USER_AGENT: str = "*"

HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/130.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.6,en;q=0.5",
    "Connection": "keep-alive",
}

# --------------------------------------------------------------------------- #
# Kategoriler
# Anahtar: komut satırında --category ile verilecek kısa ad
# Değer : (görünen ad, kategori liste sayfası URL'i)
# --------------------------------------------------------------------------- #
CATEGORIES: dict[str, tuple[str, str]] = {
    "corba": ("Çorba Tarifleri", f"{BASE_URL}/kategori/tarifler/corba-tarifleri/"),
    "et": ("Et Yemekleri", f"{BASE_URL}/kategori/tarifler/et-yemekleri/"),
    "sebze": ("Sebze Yemekleri", f"{BASE_URL}/kategori/tarifler/sebze-yemekleri/"),
    "makarna": ("Makarna Tarifleri", f"{BASE_URL}/kategori/tarifler/makarna-tarifleri/"),
    "pilav": ("Pilav Tarifleri", f"{BASE_URL}/kategori/tarifler/pilav-tarifleri/"),
    "bakliyat": ("Bakliyat Yemekleri", f"{BASE_URL}/kategori/tarifler/bakliyat-yemekleri/"),
    "salata": ("Salata, Meze, Kanepe", f"{BASE_URL}/kategori/tarifler/salata-meze-kanepe/"),
    "hamurisi": ("Hamur İşi Tarifleri", f"{BASE_URL}/kategori/tarifler/hamurisi-tarifleri/"),
    "tatli": ("Tatlı Tarifleri", f"{BASE_URL}/kategori/tarifler/tatli-tarifleri/"),
    "kahvalti": ("Kahvaltılık Tarifler", f"{BASE_URL}/kategori/tarifler/kahvaltilik-tarifleri/"),
}

# --category verilmezse taranacak kategoriler (çeşitlilik için sırayla dolaşılır).
DEFAULT_CATEGORIES: list[str] = ["corba", "et", "sebze", "tatli"]

# Sayfalama: site WordPress yapısında /page/N/ kullanıyor (1. sayfa eki yok).
# Site ?page=N yapısına geçerse burayı "?page={page}" yapmanız yeterli.
PAGINATION_PATTERN: str = "page/{page}/"
MAX_PAGES_PER_CATEGORY: int = 5

# Tarif linki gibi görünen ama tarif detay sayfası olmayan adresler.
# /video/ sayfaları farklı bir şablon kullandığı için atlanır.
EXCLUDED_LINK_PATTERNS: tuple[str, ...] = (
    "/video/",
    "/kategori/",
    "/u/",
    "/etiket/",
    "/ara/",
    "#",
)

# --------------------------------------------------------------------------- #
# HTML seçicileri (JSON-LD bulunamadığında kullanılan yedek katman)
# --------------------------------------------------------------------------- #
SELECTORS: dict[str, str] = {
    # Kategori sayfasındaki tarif kartlarının linkleri (görsel + başlık linki).
    "recipe_links": "div.recipe-cards figure.recipe-image a[href], div.recipe-cards h3 a.title[href]",
    # Tarif detay sayfasındaki başlık.
    "title": "h1.recipe-name",
    # schema.org microdata: her malzeme ayrı bir <li itemprop="recipeIngredient">.
    "ingredients": '[itemprop="recipeIngredient"]',
    # Ana görsel: önce og:image meta etiketi, yoksa tarifin ilk büyük görseli.
    "image": 'meta[property="og:image"], figure.recipe-image.single img',
    # "2-4 Kişilik" metnini içeren kısa bilgi satırı (ilk <li>).
    "servings": "ul.short-info li:first-child span.text",
    # Toplam süre microdata'sı (content="PT40M"); bulunamazsa
    # "duration_text" seçicisiyle "15dk Hazırlık, 25dk Pişirme" metni okunur.
    "duration": 'ul.short-info [itemprop="totalTime"]',
    "duration_text": "ul.short-info li:nth-of-type(2) span.text",
}

# Görsel lazy-load ise sırasıyla kontrol edilecek nitelikler.
IMAGE_ATTRIBUTES: tuple[str, ...] = ("content", "src", "data-src", "data-lazy-src", "srcset")

# --------------------------------------------------------------------------- #
# Stok görsel (fallback)
# NOT: source.unsplash.com servisi Unsplash tarafından kapatılmıştır; yayına
# almadan önce bu şablonu kendi CDN'inizdeki bir yer tutucu görselle
# değiştirmeniz önerilir. {slug} ve {index} alanları doldurulur.
# --------------------------------------------------------------------------- #
STOCK_IMAGE_URL_TEMPLATE: str = "https://source.unsplash.com/600x400/?food,{slug}&sig={index}"
