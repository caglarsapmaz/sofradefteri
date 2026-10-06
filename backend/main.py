"""
Tarif kazıyıcının giriş noktası.

Kullanım:
    python main.py                         # varsayılan kategorilerden 15 tarif
    python main.py --limit 30 --category corba tatli
    python main.py --category hepsi --output ./cikti --verbose
    python main.py --retag                 # siteye gitmeden mevcut JSON'daki malzeme etiketlerini yenile

robots.txt notu: Kazıyıcı, sitenin robots.txt kurallarına uyar; ayrıntılar
services/scraper.py dosyasının başındaki açıklamadadır.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import config
from models.recipe import Recipe, RecipeCollection
from services.scraper import RecipeScraper, ScrapeStats
from utils.ingredients import extract_tags

logger = logging.getLogger("tarif_kaziyici")

ALL_CATEGORIES_KEYWORD = "hepsi"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Komut satırı argümanlarını okur."""
    parser = argparse.ArgumentParser(
        description="nefisyemektarifleri.com'dan tarif kazıyıp recipes.json üretir.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=config.DEFAULT_LIMIT,
        help=f"Çekilecek tarif sayısı (varsayılan: {config.DEFAULT_LIMIT})",
    )
    parser.add_argument(
        "--category",
        nargs="+",
        default=config.DEFAULT_CATEGORIES,
        choices=[*config.CATEGORIES.keys(), ALL_CATEGORIES_KEYWORD],
        metavar="KATEGORI",
        help=(
            "Taranacak kategori(ler). Seçenekler: "
            f"{', '.join(config.CATEGORIES)}, {ALL_CATEGORIES_KEYWORD}. "
            f"Varsayılan: {' '.join(config.DEFAULT_CATEGORIES)}"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=config.DEFAULT_OUTPUT_DIR,
        help="Çıktı klasörü (varsayılan: backend/output)",
    )
    parser.add_argument(
        "--retag",
        action="store_true",
        help=(
            "Siteye istek atmadan mevcut recipes.json'u okuyup malzeme etiketlerini "
            "(ingredient_tags) ve tahmini besin değerlerini (nutrition) yeniden hesaplar."
        ),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Ayrıntılı (DEBUG) log çıktısı",
    )
    args = parser.parse_args(argv)
    if args.limit < 1:
        parser.error("--limit en az 1 olmalı.")
    return args


def setup_logging(verbose: bool) -> None:
    """Konsol loglamasını yapılandırır."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S",
    )
    # requests/urllib3'ün kendi DEBUG logları çıktıyı boğmasın.
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def print_summary(collection: RecipeCollection, stats: ScrapeStats, elapsed: float, json_path: Path, csv_path: Path) -> None:
    """Çalıştırma sonunda konsola özet rapor basar."""
    print()
    print("=" * 64)
    print(
        f"{stats.success} tarif başarıyla çekildi, {stats.skipped} tarif atlandı, "
        f"süre: {elapsed:.1f} sn"
    )
    print(f"  Parse yöntemi : JSON-LD {stats.jsonld_count} / HTML {stats.html_count}")
    print(f"  Stok görsel   : {stats.stock_images}")
    print(f"  HTTP isteği   : {stats.requests}, hata: {stats.errors}")
    print(f"  JSON          : {json_path}")
    print(f"  CSV           : {csv_path}")
    if stats.skipped_urls:
        print("  Atlanan URL'ler:")
        for url in stats.skipped_urls:
            print(f"    - {url}")
    print("=" * 64)


def demo_usage(collection: RecipeCollection) -> None:
    """Ödev şartını göstermek için örnek kullanım.

    Nesneler koleksiyonda "recipe1", "recipe2", ... anahtarlarıyla tutulur;
    burada aynı adlı değişkenlere atanarak doğrudan kullanılır.
    """
    if len(collection) < 3:
        print("Örnek kullanım için en az 3 tarif gerekli.")
        return

    # Koleksiyondan "recipe1", "recipe2"... anahtarlarıyla nesneleri al (__getitem__)
    recipe1 = collection["recipe1"]
    recipe2 = collection["recipe2"]
    recipe3 = collection["recipe3"]

    print("\n--- Örnek kullanım (ödev şartı) ---")
    print(recipe1)                                    # __str__ -> okunaklı çıktı
    print()
    print(repr(recipe2))                              # __repr__ -> Recipe(id=2, title='...')
    print("recipe2 malzeme sayısı:", recipe2.ingredient_count())   # normal metot
    print("recipe3 porsiyon:", recipe3.servings, "| süre:", recipe3.duration)
    print("Koleksiyondaki toplam tarif:", len(collection))         # __len__
    print("Tüm anahtarlar:", ", ".join(collection.keys()))
    print("En çok malzemeli tarif:", max(collection, key=lambda r: r.ingredient_count()).title)


def retag(output_dir: Path) -> int:
    """Kayıtlı recipes.json'u yeniden işler: metinleri normalize eder, etiketleri günceller.

    Malzeme kataloğu (utils/ingredients.py) değiştiğinde siteyi yeniden
    kazımaya gerek kalmadan JSON'u güncellemek için kullanılır.
    """
    json_path = output_dir / config.JSON_FILENAME
    if not json_path.exists():
        logger.error("Yeniden etiketlenecek dosya bulunamadı: %s", json_path)
        return 1
    data = json.loads(json_path.read_text(encoding="utf-8"))
    collection = RecipeCollection()
    for item in data.get("recipes", []):
        collection.add(Recipe.from_dict(item))

    scraped_at = datetime.fromisoformat(data["meta"]["scraped_at"]) if data.get("meta", {}).get("scraped_at") else None
    collection.to_json(json_path, scraped_at=scraped_at)
    csv_path = collection.to_csv(output_dir / config.CSV_FILENAME)

    lines = sum(r.ingredient_count() for r in collection)
    tagged = sum(1 for r in collection for line in r.ingredients if extract_tags(line))
    logger.info("%d tarif yeniden etiketlendi (%d/%d malzeme satırı tanındı).", len(collection), tagged, lines)
    logger.info("Porsiyon başına tahmini besin değerleri (nutrition) yeniden hesaplandı.")
    logger.info("Yazıldı: %s, %s", json_path, csv_path)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    setup_logging(args.verbose)

    if args.retag:
        return retag(args.output.resolve())

    categories = (
        list(config.CATEGORIES)
        if ALL_CATEGORIES_KEYWORD in args.category
        else list(dict.fromkeys(args.category))  # sırayı koruyarak tekilleştir
    )
    if args.limit < config.DEFAULT_LIMIT:
        logger.warning("Ödev şartı en az %d tarif; --limit %d verildi.", config.DEFAULT_LIMIT, args.limit)

    logger.info("Kazıma başlıyor | hedef: %d tarif | kategoriler: %s", args.limit, ", ".join(categories))
    started = time.perf_counter()
    scraped_at = datetime.now()

    try:
        # Scraper'ı oluştur ve çalıştır -> RecipeCollection döner
        with RecipeScraper(categories=categories, limit=args.limit) as scraper:
            collection = scraper.run()
            stats = scraper.stats
    except KeyboardInterrupt:
        logger.error("Kullanıcı tarafından durduruldu; dosya yazılmadı.")
        return 130

    elapsed = time.perf_counter() - started

    if len(collection) == 0:
        logger.error("Hiç tarif çekilemedi; mevcut çıktı dosyaları korunuyor.")
        print_summary(collection, stats, elapsed, Path("-"), Path("-"))
        return 1

    output_dir: Path = args.output.resolve()
    # Koleksiyonu dosyalara yaz -> output/recipes.json ve output/recipes.csv
    json_path = collection.to_json(output_dir / config.JSON_FILENAME, scraped_at=scraped_at)
    csv_path = collection.to_csv(output_dir / config.CSV_FILENAME)
    logger.info("%d kayıt yazıldı: %s", len(collection), json_path)
    logger.info("%d kayıt yazıldı: %s", len(collection), csv_path)

    print_summary(collection, stats, elapsed, json_path, csv_path)
    demo_usage(collection)
    return 0 if len(collection) >= args.limit else 2


if __name__ == "__main__":
    sys.exit(main())
