"""
nefisyemektarifleri.com için tarif kazıyıcı.

ROBOTS.TXT NOTU
---------------
Bu kazıyıcı her istekten önce sitenin robots.txt dosyasını
(urllib.robotparser ile) kontrol eder ve "*" ajanı için yasaklanan
adresleri (ör. /ara/, /u/..., *filtrele*, */populer/) ASLA istemez.
Kategori ve tarif detay sayfaları "*" kuralları altında serbesttir.

Site robots.txt içinde ayrıca "Content-Signal: ai-train=no, ai-input=no"
bildirir ve bilinen veri toplama botlarını engeller. Yani içerik sahibi,
verilerinin toplu biçimde başka yerlerde kullanılmasını istemediğini
belirtmektedir. Kazınan tarif metinleri ve özellikle görseller telif
hakkıyla korunur; çıktıyı herkese açık bir sitede yayınlamadan önce site
sahibinden izin alınmalı ve her tarifte source_url ile kaynak gösterilmelidir.

Nazik kazıma kuralları:
- İstekler arasında en az REQUEST_DELAY (1.5 sn) beklenir.
- Hata durumunda en fazla MAX_RETRIES deneme, üstel bekleme ile yapılır.
- Sadece ihtiyaç duyulan kadar sayfa istenir (--limit'e ulaşınca durur).
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Iterator, Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

import config
from models.recipe import Recipe, RecipeCollection
from utils.helpers import absolute_url

logger = logging.getLogger(__name__)


# Çalıştırma sonundaki özet rapor için sayaçlar ("15 tarif çekildi, 2 atlandı"...)
@dataclass
class ScrapeStats:
    """Çalıştırma sonunda raporlanacak sayaçlar."""

    success: int = 0
    skipped: int = 0
    errors: int = 0
    requests: int = 0
    jsonld_count: int = 0
    html_count: int = 0
    stock_images: int = 0
    skipped_urls: list[str] = field(default_factory=list)


# ====================================================================== #
# RecipeScraper SINIFI -> VERİ TOPLAYICI
# Siteye gider, sayfaları indirir, her tarif için bir Recipe nesnesi üretir
# ve hepsini bir RecipeCollection içinde döndürür.
# ====================================================================== #
class RecipeScraper:
    """Tüm kazıma mantığını kapsülleyen sınıf.

    Sorumlulukları: HTTP oturumu ve başlıklar, robots.txt kontrolü,
    yeniden deneme + üstel bekleme, kategori sayfalarından link toplama,
    tarif detay sayfasını iki katmanlı (JSON-LD -> HTML) parse etme.
    """

    def __init__(
        self,
        categories: list[str],
        limit: int = config.DEFAULT_LIMIT,
        delay: float = config.REQUEST_DELAY,
        timeout: int = config.REQUEST_TIMEOUT,
        max_retries: int = config.MAX_RETRIES,
        max_pages: int = config.MAX_PAGES_PER_CATEGORY,
    ) -> None:
        # KURUCU: ayarları kaydeder; geçersiz kategori varsa hemen hata verir
        unknown = [c for c in categories if c not in config.CATEGORIES]
        if unknown:
            raise ValueError(f"Bilinmeyen kategori(ler): {', '.join(unknown)}")

        self.categories = categories
        self.limit = limit
        self.delay = delay
        self.timeout = timeout
        self.max_retries = max_retries
        self.max_pages = max_pages

        self.session = self._build_session()      # tek HTTP oturumu (bağlantı tekrar kullanılır)
        self.stats = ScrapeStats()                # kompozisyon: scraper içinde istatistik nesnesi
        self._last_request_at: float = 0.0
        self._robots: Optional[RobotFileParser] = None

    # ------------------------------------------------------------------ #
    # Oturum ve HTTP
    # ------------------------------------------------------------------ #
    # @staticmethod: ne self ne cls alır; sınıfa ait yardımcı fonksiyon
    @staticmethod
    def _build_session() -> requests.Session:
        session = requests.Session()
        session.headers.update(config.HEADERS)
        return session

    # Nazik kazıma: istekler arasında en az 1,5 sn bekle
    def _wait_politely(self) -> None:
        """Bir önceki istekten bu yana en az self.delay saniye geçmesini sağlar."""
        elapsed = time.monotonic() - self._last_request_at
        if self._last_request_at and elapsed < self.delay:
            time.sleep(self.delay - elapsed)

    def _load_robots(self) -> None:
        """robots.txt dosyasını indirir. İndirilemezse temkinli davranıp yine de devam eder."""
        parser = RobotFileParser()
        parser.set_url(config.ROBOTS_URL)
        try:
            response = self.session.get(config.ROBOTS_URL, timeout=self.timeout)
            self._last_request_at = time.monotonic()
            self.stats.requests += 1
            response.encoding = "utf-8"
            parser.parse(response.text.splitlines())
            logger.info("robots.txt okundu: %s", config.ROBOTS_URL)
        except requests.RequestException as exc:
            # robots.txt okunamazsa kurallar boş kabul edilir; yine de
            # gecikme ve sınır kurallarıyla nazik kazıma sürer.
            logger.warning("robots.txt okunamadı, varsayılan kurallarla devam ediliyor: %s", exc)
            parser.parse([])
        self._robots = parser

    # robots.txt bu adrese izin veriyor mu?
    def is_allowed(self, url: str) -> bool:
        """URL'in robots.txt'ye göre istenebilir olup olmadığını döndürür."""
        if self._robots is None:
            self._load_robots()
        assert self._robots is not None
        return self._robots.can_fetch(config.ROBOTS_USER_AGENT, url)

    # Sayfayı indir -> BeautifulSoup nesnesi. Hata olursa 3 kez dene (1,5 -> 3 -> 6 sn bekle)
    def fetch(self, url: str) -> Optional[BeautifulSoup]:
        """URL'i indirip BeautifulSoup nesnesi döndürür.

        Geçici hatalarda (zaman aşımı, bağlantı hatası, 429/5xx) en fazla
        self.max_retries kez, her seferinde bekleme süresi ikiye katlanarak
        yeniden dener. 404 gibi kalıcı hatalarda hemen None döner.
        """
        if not self.is_allowed(url):
            logger.warning("robots.txt bu adrese izin vermiyor, atlanıyor: %s", url)
            return None

        for attempt in range(1, self.max_retries + 1):
            self._wait_politely()
            try:
                logger.debug("İstek gönderiliyor (deneme %d/%d): %s", attempt, self.max_retries, url)
                response = self.session.get(url, timeout=self.timeout)
                self._last_request_at = time.monotonic()
                self.stats.requests += 1

                if response.status_code in config.RETRY_STATUS_CODES:
                    raise requests.HTTPError(f"HTTP {response.status_code}", response=response)
                if response.status_code >= 400:
                    logger.error("Kalıcı HTTP hatası %d, tekrar denenmeyecek: %s", response.status_code, url)
                    return None

                # Türkçe karakterler bozulmasın: sunucu charset bildirmezse
                # requests ISO-8859-1 varsayar; bu durumda UTF-8'e zorlarız.
                if not response.encoding or response.encoding.lower() != "utf-8":
                    logger.debug("Kodlama '%s' -> 'utf-8' olarak düzeltildi", response.encoding)
                    response.encoding = "utf-8"

                return BeautifulSoup(response.text, "lxml")

            except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as exc:
                self._last_request_at = time.monotonic()
                if attempt == self.max_retries:
                    logger.error("%d denemenin hepsi başarısız oldu: %s (%s)", self.max_retries, url, exc)
                    return None
                backoff = self.delay * (config.BACKOFF_BASE ** (attempt - 1))
                logger.warning(
                    "İstek başarısız (%s). %.1f sn sonra tekrar denenecek (%d/%d): %s",
                    exc, backoff, attempt, self.max_retries, url,
                )
                time.sleep(backoff)
            except requests.RequestException as exc:
                logger.error("Beklenmeyen istek hatası: %s (%s)", url, exc)
                return None
        return None

    # ------------------------------------------------------------------ #
    # Link toplama
    # ------------------------------------------------------------------ #
    @staticmethod
    def _page_url(category_url: str, page: int) -> str:
        if page == 1:
            return category_url
        return category_url.rstrip("/") + "/" + config.PAGINATION_PATTERN.format(page=page)

    @staticmethod
    def _is_recipe_link(url: str) -> bool:
        parsed = urlparse(url)
        base_host = urlparse(config.BASE_URL).netloc
        if parsed.netloc != base_host:
            return False
        if parsed.path in ("", "/"):
            return False
        return not any(pattern in url for pattern in config.EXCLUDED_LINK_PATTERNS)

    # Kategori sayfasındaki tarif linklerini topla
    def extract_recipe_links(self, soup: BeautifulSoup) -> list[str]:
        """Bir liste sayfasındaki tarif linklerini sırasını koruyarak, tekil biçimde çıkarır."""
        links: list[str] = []
        seen: set[str] = set()
        for anchor in soup.select(config.SELECTORS["recipe_links"]):
            url = absolute_url(anchor.get("href", "")).split("#", 1)[0]
            if url not in seen and self._is_recipe_link(url):
                seen.add(url)
                links.append(url)
        return links

    # Kategorinin sayfalarını (sayfa 1, 2, 3...) gezerek linkleri tek tek ver
    def iter_category_links(self, category_key: str) -> Iterator[str]:
        """Bir kategorinin sayfalarını tembel (lazy) biçimde gezerek tarif linkleri üretir.

        Yeni sayfa ancak önceki sayfadaki linkler tükendiğinde istenir.
        """
        name, category_url = config.CATEGORIES[category_key]
        seen: set[str] = set()
        for page in range(1, self.max_pages + 1):
            page_url = self._page_url(category_url, page)
            logger.info("Kategori sayfası kazınıyor: %s (%s, sayfa %d)", page_url, name, page)
            soup = self.fetch(page_url)
            if soup is None:
                self.stats.errors += 1
                return
            links = [link for link in self.extract_recipe_links(soup) if link not in seen]
            if not links:
                logger.info("'%s' kategorisinde yeni tarif linki kalmadı.", name)
                return
            logger.info("%d tarif linki bulundu (%s, sayfa %d)", len(links), name, page)
            seen.update(links)
            yield from links

    # ------------------------------------------------------------------ #
    # Detay sayfası parse
    # ------------------------------------------------------------------ #
    # Sayfadaki <script type="application/ld+json"> içinde "Recipe" bloğunu ara
    @staticmethod
    def find_jsonld_recipe(soup: BeautifulSoup) -> Optional[dict[str, Any]]:
        """<script type="application/ld+json"> etiketleri içinde @type == "Recipe" bloğunu bulur.

        Blok doğrudan, bir liste içinde ya da "@graph" altında olabilir.
        """
        for script in soup.find_all("script", type="application/ld+json"):
            raw = script.string or script.get_text()
            if not raw or not raw.strip():
                continue
            try:
                data = json.loads(raw.strip())
            except json.JSONDecodeError as exc:
                logger.debug("Bozuk JSON-LD bloğu atlandı: %s", exc)
                continue
            found = _search_recipe_node(data)
            if found:
                return found
        return None

    # TEK TARİF: sayfayı indir -> önce JSON-LD dene, yoksa HTML -> Recipe nesnesi döndür
    def parse_recipe(self, url: str, index: int, category: str) -> Optional[Recipe]:
        """Tarif detay sayfasını indirir ve Recipe nesnesine çevirir.

        1) JSON-LD (schema.org Recipe) varsa öncelikli olarak kullanılır.
        2) JSON-LD yoksa ya da eksik alan varsa HTML seçicileriyle tamamlanır.
        """
        soup = self.fetch(url)
        if soup is None:
            self.stats.errors += 1
            return None

        jsonld = self.find_jsonld_recipe(soup)
        if jsonld:
            recipe = Recipe.from_jsonld(jsonld, url, index, category)
            if recipe.missing_fields():
                logger.debug("JSON-LD eksik alanlar: %s -> HTML ile tamamlanıyor", recipe.missing_fields())
                recipe.fill_missing_from(Recipe.from_soup(soup, url, index, category))
        else:
            recipe = Recipe.from_soup(soup, url, index, category)

        logger.info("Parse yöntemi: %-11s | %s", recipe.parse_method, url)
        return recipe

    # ------------------------------------------------------------------ #
    # Ana akış
    # ------------------------------------------------------------------ #
    def _round_robin_links(self) -> Iterator[tuple[str, str]]:
        """Kategorileri sırayla dolaşarak (kategori adı, link) çiftleri üretir.

        Böylece --limit 15 ile 4 kategori verildiğinde tüm tarifler tek
        kategoriden gelmez; çıktı frontend filtrelemesi için çeşitli olur.
        """
        iterators = {key: self.iter_category_links(key) for key in self.categories}
        while iterators:
            for key in list(iterators):
                try:
                    yield config.CATEGORIES[key][0], next(iterators[key])
                except StopIteration:
                    del iterators[key]

    # ANA AKIŞ: 3 sınıfın birlikte çalıştığı yer
    def run(self) -> RecipeCollection:
        """Limit dolana ya da kaynak tükenene kadar tarifleri kazır."""
        collection = RecipeCollection()                      # 1) boş tarif kutusu
        self._load_robots()

        for category_name, url in self._round_robin_links():
            if len(collection) >= self.limit:
                break
            if collection.contains_url(url):
                continue

            index = len(collection) + 1                     # bu tarifin numarası -> recipe{index}
            try:
                recipe = self.parse_recipe(url, index, category_name)   # 2) Recipe nesnesi üret
            except Exception as exc:  # noqa: BLE001 - tek tarif tüm scripti çökertmemeli
                logger.exception("Tarif işlenirken beklenmeyen hata, atlanıyor: %s (%s)", url, exc)
                self.stats.errors += 1
                self.stats.skipped += 1
                self.stats.skipped_urls.append(url)
                continue

            if recipe is None:
                self.stats.skipped += 1
                self.stats.skipped_urls.append(url)
                continue
            if not recipe.is_valid():
                logger.warning("Zorunlu alan eksik (%s), tarif atlandı: %s", ", ".join(recipe.missing_fields()), url)
                self.stats.skipped += 1
                self.stats.skipped_urls.append(url)
                continue

            if collection.add(recipe):                      # 3) kutuya ekle (tekrar değilse)
                self.stats.success += 1
                if recipe.parse_method.startswith("jsonld"):
                    self.stats.jsonld_count += 1
                else:
                    self.stats.html_count += 1
                if recipe.image_source == "stock":
                    self.stats.stock_images += 1
                    logger.warning("Görsel bulunamadı, stok görsel atandı: %s", recipe.title)
                logger.info(
                    "[%d/%d] Eklendi: %s (%d malzeme)",
                    len(collection), self.limit, recipe.title, recipe.ingredient_count(),
                )
                # Limit dolduysa hemen çık; aksi halde bir sonraki link için
                # gereksiz yere yeni bir kategori sayfası istenebilir.
                if len(collection) >= self.limit:
                    break

        if len(collection) < self.limit:
            logger.warning(
                "Hedeflenen %d tarife ulaşılamadı, %d tarif toplandı. "
                "MAX_PAGES_PER_CATEGORY değerini artırmayı ya da kategori eklemeyi deneyin.",
                self.limit, len(collection),
            )
        return collection

    def close(self) -> None:
        """HTTP oturumunu kapatır."""
        self.session.close()

    # with RecipeScraper(...) as scraper: -> blok bitince oturum otomatik kapanır
    def __enter__(self) -> "RecipeScraper":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def _search_recipe_node(data: Any) -> Optional[dict[str, Any]]:
    """JSON-LD ağacında @type'ı "Recipe" olan ilk düğümü özyinelemeli olarak arar."""
    if isinstance(data, list):
        for item in data:
            found = _search_recipe_node(item)
            if found:
                return found
    elif isinstance(data, dict):
        node_type = data.get("@type")
        types = node_type if isinstance(node_type, list) else [node_type]
        if "Recipe" in types:
            return data
        if "@graph" in data:
            return _search_recipe_node(data["@graph"])
    return None
