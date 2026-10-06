"""Recipe (tek tarif) ve RecipeCollection (tarif koleksiyonu) sınıfları."""

from __future__ import annotations

import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Optional, Union

from bs4 import BeautifulSoup, Tag

from config import DEFAULT_VALUE, IMAGE_ATTRIBUTES, SELECTORS, SOURCE_NAME
from utils.ingredients import GROUPS, INGREDIENT_CATALOG, extract_ingredient_tags
from utils.nutrition import estimate_nutrition
from utils.helpers import (
    absolute_url,
    build_image_url,
    clean_text,
    first_url_from_srcset,
    format_minutes,
    is_valid_image_url,
    normalize_servings,
    parse_duration_text,
    parse_iso_duration,
    slugify,
)

logger = logging.getLogger(__name__)


# ====================================================================== #
# Recipe SINIFI -> TEK BİR TARİF
# Her nesne bir yemeği temsil eder: başlık, malzemeler, görsel, porsiyon...
# Görevi: veriyi tutmak, temizlemek ve kendini JSON'a çevirmek.
# ====================================================================== #
class Recipe:
    """Kazınan tek bir yemek tarifini temsil eder.

    Tüm alanlar her zaman dolu tutulur; veri yoksa DEFAULT_VALUE
    ("Bilgi bulunamadı") yazılır. Böylece JSON çıktısında hiçbir alan null olmaz.
    """

    def __init__(
        self,
        id: int,
        title: str,
        ingredients: list[str],
        image_url: str,
        servings: str,
        duration: str,
        slug: str,
        source_url: str,
        image_source: str = "scraped",
        duration_minutes: int = 0,
        category: str = DEFAULT_VALUE,
        parse_method: str = "html",
    ) -> None:
        # KURUCU METOT: Recipe(...) yazıldığında otomatik çalışır.
        # self.xxx = ... satırları değeri nesnenin içine kaydeder (nesne nitelikleri).
        self.id: int = id                                              # sıra numarası (1, 2, 3...)
        self.title: str = clean_text(title) or DEFAULT_VALUE           # boşsa "Bilgi bulunamadı"
        self.ingredients: list[str] = [i for i in (clean_text(x) for x in ingredients) if i]  # temizle, boşları at
        self.slug: str = slug or slugify(self.title)                   # "Mercimek Çorbası" -> "mercimek-corbasi"
        self.servings: str = servings or DEFAULT_VALUE
        self.duration: str = duration or DEFAULT_VALUE
        self.duration_minutes: int = max(0, int(duration_minutes or 0))
        self.source_url: str = source_url
        self.category: str = category or DEFAULT_VALUE
        # Hangi katmanla parse edildiği ("jsonld", "html" veya "jsonld+html"); sadece loglama için.
        self.parse_method: str = parse_method

        # Görsel geçersizse deterministik stok görsele düş.
        if is_valid_image_url(image_url):
            self.image_url: str = image_url
            self.image_source: str = image_source
        else:
            self.image_url = build_image_url(self.title, self.id)
            self.image_source = "stock"

    # ------------------------------------------------------------------ #
    # Sihirli metotlar
    # ------------------------------------------------------------------ #
    def __str__(self) -> str:
        # print(recipe1) yazınca çalışır -> kullanıcıya okunaklı çıktı
        lines = [
            f"#{self.id} {self.title}",
            f"  Porsiyon : {self.servings}",
            f"  Süre     : {self.duration}",
            f"  Malzeme  : {self.ingredient_count()} adet",
            f"  Görsel   : {self.image_url} ({self.image_source})",
            f"  Kaynak   : {self.source_url}",
        ]
        return "\n".join(lines)

    def __repr__(self) -> str:
        # Geliştirici için kısa teknik özet -> Recipe(id=1, title='...')
        return f"Recipe(id={self.id}, title={self.title!r})"

    # İki tarif aynı mı? Kaynak URL'leri aynıysa evet.
    def __eq__(self, other: object) -> bool:
        return isinstance(other, Recipe) and self.source_url == other.source_url

    def __hash__(self) -> int:
        return hash(self.source_url)

    # ------------------------------------------------------------------ #
    # Genel metotlar
    # ------------------------------------------------------------------ #
    def ingredient_count(self) -> int:
        # Ödev şartı: malzeme sayısı -> recipe2.ingredient_count()
        """Malzeme sayısını döndürür."""
        return len(self.ingredients)

    # @property: metot gibi yazılır, değişken gibi kullanılır -> recipe.ingredient_tags
    @property
    def ingredient_tags(self) -> list[str]:
        """Malzeme satırlarından çıkarılan standart malzeme adları (ör. "mercimek", "soğan").

        "Dolabımda ne var?" özelliği bu listeyi kullanıcının seçtikleriyle karşılaştırır.
        """
        return extract_ingredient_tags(self.ingredients)

    @property
    def nutrition(self) -> dict[str, Any]:
        """Porsiyon başına TAHMİNİ kalori ve makrolar (bkz. utils/nutrition.py).

        Kaynak site besin değeri vermediği için malzeme miktarlarından hesaplanır.
        """
        return estimate_nutrition(self.ingredients, self.servings)

    # "recipe1", "recipe2"... anahtarı burada üretilir (id'den)
    @property
    def key(self) -> str:
        """Ödev şartındaki "recipe1", "recipe2" ... adlandırmasına karşılık gelen anahtar."""
        return f"recipe{self.id}"

    # Başlığı ya da malzemesi olmayan tarif geçersiz sayılır ve atlanır
    def is_valid(self) -> bool:
        """Frontend için kullanılabilir mi? Başlık ve en az bir malzeme zorunludur."""
        return self.title != DEFAULT_VALUE and self.ingredient_count() > 0

    def missing_fields(self) -> list[str]:
        """Varsayılan değerde kalan (yani kazınamayan) alanların listesi."""
        missing: list[str] = []
        if self.title == DEFAULT_VALUE:
            missing.append("title")
        if not self.ingredients:
            missing.append("ingredients")
        if self.image_source == "stock":
            missing.append("image_url")
        if self.servings == DEFAULT_VALUE:
            missing.append("servings")
        if self.duration == DEFAULT_VALUE:
            missing.append("duration")
        return missing

    # JSON-LD'de eksik kalan alanları HTML'den okunan ikinci bir nesneyle tamamlar
    def fill_missing_from(self, other: "Recipe") -> None:
        """JSON-LD'den eksik kalan alanları HTML'den okunan başka bir Recipe ile tamamlar."""
        if self.title == DEFAULT_VALUE and other.title != DEFAULT_VALUE:
            self.title = other.title
            self.slug = other.slug
        if not self.ingredients and other.ingredients:
            self.ingredients = list(other.ingredients)
        if self.image_source == "stock" and other.image_source == "scraped":
            self.image_url, self.image_source = other.image_url, other.image_source
        if self.servings == DEFAULT_VALUE:
            self.servings = other.servings
        if self.duration == DEFAULT_VALUE:
            self.duration = other.duration
            self.duration_minutes = other.duration_minutes
        self.parse_method = f"{self.parse_method}+{other.parse_method}"

    # NESNE -> SÖZLÜK: json.dump nesneyi yazamaz, sözlüğü yazabilir (serileştirme).
    # recipes.json'daki HER TARİF bu sözlükten oluşur.
    def to_dict(self) -> dict[str, Any]:
        """JSON serileştirme için sözlük döndürür. Alan sırası frontend sözleşmesidir."""
        return {
            "id": self.id,                                  # sıra numarası
            "key": self.key,                                # "recipe1" -> ödevdeki adlandırma
            "slug": self.slug,                              # detay sayfası adresi: #/tarif/mercimek-corbasi
            "title": self.title,                            # yemeğin adı
            "category": self.category,                      # filtreleme için kategori
            "ingredients": list(self.ingredients),          # malzemeler, her biri ayrı satır
            "ingredient_count": self.ingredient_count(),    # malzeme sayısı
            "ingredient_tags": self.ingredient_tags,        # sade malzeme adları -> "dolabımda ne var?"
            "nutrition": self.nutrition,                    # tahmini kalori/makro -> "makro hesapla"
            "servings": self.servings,                      # "4-6 kişilik"
            "duration": self.duration,                      # "40 dakika" (ekranda gösterilir)
            "duration_minutes": self.duration_minutes,      # 40 (süreye göre filtre için sayı)
            "image_url": self.image_url,                    # yemeğin görseli
            "image_source": self.image_source,              # "scraped" (siteden) / "stock" (yedek)
            "source_url": self.source_url,                  # orijinal tarif adresi (kaynak gösterme)
        }

    # ------------------------------------------------------------------ #
    # Fabrika metotları
    # ------------------------------------------------------------------ #
    # @classmethod = FABRİKA METODU: self değil cls (sınıfın kendisi) alır,
    # sonunda return cls(...) ile YENİ BİR NESNE üretir.
    # Veri 3 farklı kaynaktan gelebildiği için 3 fabrika var:
    #   from_dict   -> kayıtlı recipes.json'dan
    #   from_jsonld -> sayfadaki JSON-LD verisinden
    #   from_soup   -> HTML'den (CSS selector ile)
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Recipe":
        """to_dict() çıktısından nesneyi geri kurar (kayıtlı JSON'u yeniden işlemek için)."""
        return cls(
            id=int(data["id"]),
            title=data.get("title", DEFAULT_VALUE),
            ingredients=list(data.get("ingredients", [])),
            image_url=data.get("image_url", ""),
            servings=data.get("servings", DEFAULT_VALUE),
            duration=data.get("duration", DEFAULT_VALUE),
            duration_minutes=int(data.get("duration_minutes", 0) or 0),
            slug=data.get("slug", ""),
            source_url=data.get("source_url", ""),
            image_source=data.get("image_source", "scraped"),
            category=data.get("category", DEFAULT_VALUE),
            parse_method="json",
        )

    @classmethod
    def from_jsonld(
        cls, data: dict[str, Any], url: str, index: int, category: str = DEFAULT_VALUE
    ) -> "Recipe":
        """schema.org Recipe JSON-LD bloğundan nesne üretir (öncelikli ve en dayanıklı yöntem)."""
        title = clean_text(_as_text(data.get("name"))) or DEFAULT_VALUE

        raw_ingredients = data.get("recipeIngredient") or data.get("ingredients") or []
        if isinstance(raw_ingredients, str):
            raw_ingredients = [raw_ingredients]
        ingredients = [clean_text(_as_text(i)) for i in raw_ingredients]

        image_url = _image_from_jsonld(data.get("image"))

        servings = DEFAULT_VALUE
        recipe_yield = data.get("recipeYield")
        if isinstance(recipe_yield, list):
            recipe_yield = recipe_yield[0] if recipe_yield else None
        if recipe_yield not in (None, ""):
            servings = normalize_servings(str(recipe_yield))

        minutes = parse_iso_duration(_as_text(data.get("totalTime")))
        if not minutes:
            minutes = parse_iso_duration(_as_text(data.get("prepTime"))) + parse_iso_duration(
                _as_text(data.get("cookTime"))
            )

        return cls(
            id=index,
            title=title,
            ingredients=ingredients,
            image_url=image_url,
            servings=servings,
            duration=format_minutes(minutes),
            duration_minutes=minutes,
            slug=slugify(title) if title != DEFAULT_VALUE else "",
            source_url=url,
            category=category,
            parse_method="jsonld",
        )

    @classmethod
    def from_soup(
        cls, soup: BeautifulSoup, url: str, index: int, category: str = DEFAULT_VALUE
    ) -> "Recipe":
        """HTML'den config.SELECTORS kullanarak nesne üretir (yedek yöntem).

        Her alan kendi try/except bloğunda okunur; bir alanın bozuk olması
        diğer alanların okunmasını engellemez.
        """
        # 1) Başlık: <h1 class="recipe-name"> (selector config.py'den gelir)
        title = DEFAULT_VALUE
        try:
            el = soup.select_one(SELECTORS["title"])
            if el:
                title = clean_text(el.get_text(" ")) or DEFAULT_VALUE
        except Exception as exc:  # noqa: BLE001 - tek alan hatası tüm tarifi düşürmemeli
            logger.debug("Başlık okunamadı (%s): %s", url, exc)

        # 2) Malzemeler: her <li itemprop="recipeIngredient"> bir malzeme
        ingredients: list[str] = []
        try:
            ingredients = [clean_text(el.get_text(" ")) for el in soup.select(SELECTORS["ingredients"])]
        except Exception as exc:  # noqa: BLE001
            logger.debug("Malzemeler okunamadı (%s): %s", url, exc)

        # 3) Görsel: önce og:image, yoksa sayfadaki ana <img>
        image_url = ""
        try:
            image_url = _image_from_soup(soup)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Görsel okunamadı (%s): %s", url, exc)

        # 4) Porsiyon: "2-4 Kişilik" -> "2-4 kişilik"
        servings = DEFAULT_VALUE
        try:
            el = soup.select_one(SELECTORS["servings"])
            if el:
                servings = normalize_servings(el.get_text(" "))
        except Exception as exc:  # noqa: BLE001
            logger.debug("Porsiyon okunamadı (%s): %s", url, exc)

        # 5) Süre: "PT40M" -> 40 dakika
        minutes = 0
        try:
            el = soup.select_one(SELECTORS["duration"])
            if el:
                minutes = parse_iso_duration(el.get("content") or el.get_text())
            if not minutes:
                el = soup.select_one(SELECTORS["duration_text"])
                if el:
                    minutes = parse_duration_text(el.get_text(" "))
        except Exception as exc:  # noqa: BLE001
            logger.debug("Süre okunamadı (%s): %s", url, exc)

        # Okunan değerlerle yeni bir Recipe nesnesi üret
        return cls(
            id=index,
            title=title,
            ingredients=ingredients,
            image_url=image_url,
            servings=servings,
            duration=format_minutes(minutes),
            duration_minutes=minutes,
            slug=slugify(title) if title != DEFAULT_VALUE else "",
            source_url=url,
            category=category,
            parse_method="html",
        )


# ====================================================================== #
# RecipeCollection SINIFI -> TARİF KUTUSU
# Tarifleri {"recipe1": <Recipe>, "recipe2": <Recipe>, ...} sözlüğünde tutar.
# Görevi: tekrarı engellemek, liste gibi kullanılmak, JSON/CSV dosyası yazmak.
# ====================================================================== #
class RecipeCollection:
    """Tarifleri "recipe1", "recipe2", ... anahtarlarıyla tutan koleksiyon.

    Neden bu yapı?
    - Ödev şartı, her tarif nesnesinin recipe1, recipe2, recipe3 ... şeklinde
      isimlendirilmesini istiyor. Python'da döngü içinde dinamik değişken adı
      üretmek (globals()/exec ile) kötü bir pratiktir: hata ayıklaması zordur,
      IDE/type checker tarafından görülmez ve isim çakışmalarına açıktır.
    - Bunun yerine aynı isimleri bir sözlüğün ANAHTARI olarak kullanıyoruz:
      {"recipe1": <Recipe>, "recipe2": <Recipe>, ...}. Böylece hem ödevdeki
      adlandırma birebir korunur, hem de koleksiyon üzerinde döngü, uzunluk,
      indeksleme gibi işlemler güvenle yapılır.
    - Aynı "key" değeri JSON çıktısına da yazılır; frontend tarafı tıklanan
      kartı bu anahtar (ya da slug) ile eşleştirebilir.
    - Python 3.7+ sözlükleri ekleme sırasını koruduğu için id sırası da korunur.
    - URL'ler ayrıca bir kümede (set) tutulur; aynı tarif iki kez eklenemez.
    """

    def __init__(self) -> None:
        # Baştaki "_" -> iç kullanım (kapsülleme): dışarıdan değil add() ile eklenir
        self._items: dict[str, Recipe] = {}   # "recipe1" -> Recipe nesnesi
        self._urls: set[str] = set()          # eklenen URL'ler (tekrar kontrolü için)

    # Tarif ekler; aynı URL daha önce eklendiyse False döner (tekilleştirme)
    def add(self, recipe: Recipe) -> bool:
        """Tarifi ekler. Aynı kaynak URL daha önce eklendiyse False döner."""
        normalized = _normalize_url(recipe.source_url)
        if normalized in self._urls:
            logger.info("Tekrarlayan tarif atlandı: %s", recipe.source_url)
            return False
        # Aynı ada sahip farklı tarifler olabilir; slug frontend'de detay
        # sayfası adresi olacağı için benzersiz olmalı ("-2", "-3" eki).
        used_slugs = {r.slug for r in self._items.values()}
        base_slug, suffix = recipe.slug, 2
        while recipe.slug in used_slugs:
            recipe.slug = f"{base_slug}-{suffix}"
            suffix += 1
        self._items[recipe.key] = recipe      # "recipe1": <Recipe> olarak kaydet
        self._urls.add(normalized)
        return True

    def contains_url(self, url: str) -> bool:
        """Verilen URL koleksiyonda var mı?"""
        return _normalize_url(url) in self._urls

    def all(self) -> list[Recipe]:
        """Tüm tarifleri ekleme sırasıyla döndürür."""
        return list(self._items.values())

    def keys(self) -> list[str]:
        """"recipe1", "recipe2" ... anahtarlarını döndürür."""
        return list(self._items.keys())

    # Sihirli metotlar: koleksiyon Python listesi/sözlüğü gibi kullanılabilsin
    def __len__(self) -> int:                       # len(collection)
        return len(self._items)

    def __iter__(self) -> Iterator[Recipe]:         # for r in collection:
        return iter(self._items.values())

    def __getitem__(self, key: Union[str, int]) -> Recipe:   # collection["recipe1"]
        """collection["recipe1"] ya da collection[0] (sıra numarası) ile erişim sağlar."""
        if isinstance(key, int):
            return self.all()[key]
        return self._items[key]

    def __contains__(self, key: object) -> bool:    # "recipe3" in collection
        return key in self._items

    def __repr__(self) -> str:
        return f"RecipeCollection(total={len(self)})"

    # recipes.json'un TAMAMI burada oluşur: üstte "meta" (bilgi), altta "recipes" (liste)
    def to_dict(self, scraped_at: Optional[datetime] = None) -> dict[str, Any]:
        """Frontend'in tüketeceği {"meta": ..., "recipes": [...]} yapısını üretir."""
        scraped_at = scraped_at or datetime.now()
        return {
            "meta": {
                "source": SOURCE_NAME,                                        # veri kaynağı
                "scraped_at": scraped_at.replace(microsecond=0).isoformat(),  # ne zaman çekildi
                "total": len(self),                                           # kaç tarif var
                "ingredient_groups": list(GROUPS),                            # malzeme grupları (sebze, meyve...)
                "ingredients": self.ingredient_index(),                       # "dolabımda ne var?" malzeme listesi
            },
            "recipes": [recipe.to_dict() for recipe in self],                 # her tarif kendini sözlüğe çevirir
        }

    def ingredient_index(self) -> list[dict[str, Any]]:
        """Koleksiyonda geçen tüm malzemelerin listesi: ad, grup, temel mi, kaç tarifte geçtiği.

        Frontend "dolabımda ne var?" ekranındaki seçilebilir malzemeleri buradan üretir.
        """
        counts: dict[str, int] = {}
        for recipe in self:
            for tag in recipe.ingredient_tags:
                counts[tag] = counts.get(tag, 0) + 1
        rows = [
            {
                "name": name,
                "group": INGREDIENT_CATALOG[name].group,
                "staple": INGREDIENT_CATALOG[name].staple,
                "count": count,
            }
            for name, count in counts.items()
        ]
        rows.sort(key=lambda r: (GROUPS.index(r["group"]), -r["count"], r["name"]))
        return rows

    def to_json(self, path: Union[str, Path], scraped_at: Optional[datetime] = None) -> Path:
        """Koleksiyonu UTF-8, ensure_ascii=False, indent=2 ile JSON dosyasına yazar.

        Önce geçici dosyaya yazıp sonra yer değiştirir; yarıda kalan bir
        çalıştırma eski ve sağlam recipes.json dosyasını bozmaz.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)              # output/ klasörü yoksa oluştur
        tmp_path = path.with_suffix(path.suffix + ".tmp")           # önce geçici dosyaya yaz
        with tmp_path.open("w", encoding="utf-8") as fh:
            # ensure_ascii=False -> "ç" olarak yazar (\u00e7 değil) | indent=2 -> okunaklı girinti
            json.dump(self.to_dict(scraped_at), fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        tmp_path.replace(path)                                      # sonra asıl dosyanın yerine koy
        return path

    def to_csv(self, path: Union[str, Path]) -> Path:
        """Koleksiyonu CSV olarak yazar. Malzemeler " | " ile birleştirilir.

        Excel'de Türkçe karakterlerin doğru görünmesi için utf-8-sig (BOM) kullanılır.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = [recipe.to_dict() for recipe in self]                # JSON ile aynı veri
        fieldnames = list(_CSV_FIELDS)                              # CSV sütun başlıkları
        with path.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                row["ingredients"] = " | ".join(row["ingredients"])
                row["ingredient_tags"] = ", ".join(row["ingredient_tags"])
                nutrition = row.pop("nutrition")
                row.update({
                    "calories": nutrition["calories"],
                    "protein_g": nutrition["protein"],
                    "carbs_g": nutrition["carbs"],
                    "fat_g": nutrition["fat"],
                })
                writer.writerow(row)
        return path


# ---------------------------------------------------------------------- #
# Modül içi yardımcılar
# ---------------------------------------------------------------------- #
_CSV_FIELDS: tuple[str, ...] = (
    "id", "key", "slug", "title", "category", "ingredients", "ingredient_count", "ingredient_tags",
    "calories", "protein_g", "carbs_g", "fat_g",
    "servings", "duration", "duration_minutes", "image_url", "image_source", "source_url",
)


def _normalize_url(url: str) -> str:
    """Tekilleştirme için URL'i sadeleştirir (sorgu, parça ve sondaki / kaldırılır)."""
    return url.split("#", 1)[0].split("?", 1)[0].rstrip("/").lower()


def _as_text(value: Any) -> str:
    """JSON-LD alanları bazen sözlük ya da liste olabilir; metne indirger."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return str(value.get("text") or value.get("name") or value.get("@value") or "")
    if isinstance(value, list):
        return _as_text(value[0]) if value else ""
    return str(value)


def _image_from_jsonld(image: Any) -> str:
    """JSON-LD "image" alanı str, liste ya da ImageObject olabilir; ilk geçerli URL'i döner."""
    if isinstance(image, str):
        return absolute_url(image) if image else ""
    if isinstance(image, dict):
        return _image_from_jsonld(image.get("url") or image.get("contentUrl"))
    if isinstance(image, list):
        for item in image:
            url = _image_from_jsonld(item)
            if is_valid_image_url(url):
                return url
    return ""


def _image_from_soup(soup: BeautifulSoup) -> str:
    """og:image ya da ana <img> etiketinden görsel URL'i okur.

    Lazy-load ihtimaline karşı content, src, data-src, data-lazy-src ve srcset
    nitelikleri sırasıyla denenir; "data:" ile başlayan yer tutucular atlanır.
    """
    for el in soup.select(SELECTORS["image"]):
        url = _image_from_tag(el)
        if is_valid_image_url(url):
            return url
    return ""


def _image_from_tag(el: Tag) -> str:
    for attr in IMAGE_ATTRIBUTES:
        value = el.get(attr)
        if not value or not isinstance(value, str):
            continue
        if attr == "srcset":
            value = first_url_from_srcset(value)
        value = value.strip()
        if value and not value.startswith("data:"):
            return absolute_url(value)
    return ""
