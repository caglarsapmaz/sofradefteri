# sofra defteri — Tarif Sitesi

> **Not:** Bu proje **Nesne Tabanlı Programlama** dersi için yapılmıştır.
> Herhangi bir kâr amacı gütmemektedir.

Canlı site: https://sofradefteri.vercel.app · Genel tanıtım için repo kökündeki
[README](../README.md) dosyasına bakın. Bu dosya ayrıntılı teknik belgedir.

nefisyemektarifleri.com kategori sayfalarından tarifleri BeautifulSoup ile kazıyıp
frontend'in doğrudan okuyacağı `backend/output/recipes.json` (ve `recipes.csv`) dosyasını üretir.
Sunucu, API ya da arayüz katmanı yoktur; çalıştırılır, JSON üretir, biter.

## Kurulum

Python 3.10 veya üzeri gerekir.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Çalıştırma

```bash
cd backend
python main.py
```

Seçenekler:

| Seçenek | Açıklama | Varsayılan |
|---|---|---|
| `--limit N` | Çekilecek tarif sayısı | 15 |
| `--category K [K ...]` | Kategori kısa adları (`corba`, `et`, `sebze`, `makarna`, `pilav`, `bakliyat`, `salata`, `hamurisi`, `tatli`, `kahvalti`) ya da `hepsi` | `corba et sebze tatli` |
| `--output KLASOR` | JSON/CSV'nin yazılacağı klasör | `backend/output` |
| `--verbose` | Ayrıntılı (DEBUG) log | kapalı |

| `--retag` | Siteye istek atmadan mevcut `recipes.json`'daki malzeme etiketlerini ve tahmini besin değerlerini yeniden hesaplar | kapalı |

Örnek: `python main.py --limit 30 --category corba tatli --verbose`

Birden fazla kategori verildiğinde tarifler kategoriler arasında sırayla alınır, yani 15 tarif tek kategoriden gelmez.
15 tarif yaklaşık 35-40 saniye sürer (istekler arasında 1.5 sn bekleme var).

Çıkış kodları: `0` başarılı, `1` hiç tarif çekilemedi (eski JSON korunur), `2` limitin altında tarif çekildi.

## Frontend (sofra defteri)

`frontend/` klasörü, `recipes.json` dosyasını okuyan, derleme adımı gerektirmeyen düz HTML/CSS/JS arayüzüdür.

```
frontend/
  index.html       sayfa iskeleti (duyuru şeridi, header, karusel, filtre, ızgara, footer)
  css/style.css    tüm stiller; renkler :root değişkenlerinde
  js/icons.js      kategori dairelerindeki çizim ikonları (satır içi SVG)
  js/app.js        veri yükleme, filtreleme, sayfalama, arama, hash yönlendirme
```

### Çalıştırma

Tarayıcı, `file://` ile açılan sayfadan JSON okuyamaz; bu yüzden **repo kökünden** yerel sunucuyu başlatın:

```bash
python serve.py
```

Ardından http://localhost:8137 adresini açın.

Site History API ile temiz adresler kullanır (`/`, `/dolabim`, `/makro`, `/hakkinda`, `/iletisim`,
`/tarif/<slug>`); sayfalar arası geçişte sayfa yenilenmez. Bu adreslere doğrudan girildiğinde ya da
sayfa yenilendiğinde `frontend/index.html` sunulmalıdır: yerelde `serve.py`, Vercel'de `vercel.json`
bunu yapar. Bu yüzden `python -m http.server` yerine `serve.py` kullanılmalıdır. Eski
`/frontend/#/...` bağlantıları açılışta otomatik olarak yeni adrese çevrilir.
Veriyi yenilemek için `backend` içinde `python main.py --category hepsi --limit 60` çalıştırıp sayfayı yenilemeniz yeterli.

### Özellikler

- **Kategori karuseli**: "tümü", veride bulunan her kategori, "30 dk tarifleri" ve "< 9 malzeme" kısayolları. Oklarla kaydırılır; tıklanan daire tek filtre olarak uygulanır, tekrar tıklanınca kaldırılır.
- **Filtre paneli**: kategori, süre (`duration_minutes`), malzeme sayısı (`ingredient_count`), kişi sayısı (`servings`). Grup içinde "veya", gruplar arasında "ve" mantığı; parantez içindeki sayılar diğer seçimlere göre canlı hesaplanır.
- **Arama** (büyüteç ikonu): tarif adında ve malzemelerde arar (ör. "kıyma").
- **Sayfalama**: sayfa başına 12 tarif.
- **Detay sayfası** (`/tarif/<slug>`): görsel, porsiyon/süre/malzeme sayısı, işaretlenebilir malzeme listesi, orijinal tarife bağlantı ve aynı kategoriden 4 öneri. Adres paylaşılabilir; dizine dönünce filtreler ve kaydırma konumu korunur.
- `image_source` "stock" ise ya da görsel yüklenemezse kategori ikonlu yer tutucu gösterilir.
- Mobilde menü ve filtre paneli açılır-kapanır düğmelere dönüşür; ızgara 2 sütuna iner.
- Kazınan tüm metinler ekrana basılmadan önce HTML kaçışından geçirilir.
- Bülten formu yalnızca e-posta doğrulaması yapar; sunucu katmanı olmadığı için veri gönderilmez.

### Dolabımda ne var? (`/dolabim`)

Evdeki malzemeleri seçerek yapılabilecek tarifleri bulur. Menüden ya da kategori karuselindeki buzdolabı ikonundan açılır.

1. **Backend** her malzeme satırından standart malzeme adını çıkarır (`backend/utils/ingredients.py`):
   "1 su bardağı kırmızı mercimek" → `mercimek`, "2 yemek kaşığı biber salçası" → `biber salçası`,
   "tereyağı veya margarin" → `tereyağı`. Ölçü birimleri ("su bardağı", "yemek kaşığı"...) önce silinir, uzun kalıplar
   önce aranır ("biber salçası", "biber"den önce), eşleşen kelime ekiyle birlikte tüketilir ("limonun" içindeki "-un" un sayılmaz).
   Sonuç her tarifte `ingredient_tags` alanına, malzeme listesi (grup, kaç tarifte geçtiği, temel malzeme mi) `meta.ingredients` alanına yazılır.
   Mevcut veride 680 malzeme satırının 680'i tanınıyor.
2. **Frontend** seçilen malzemeleri her tarifin `ingredient_tags` listesiyle karşılaştırır ve sonuçları iki grupta gösterir:
   **hemen yapabilirsin** (eksik yok) ve **2 malzemeye kadar eksik** (eksikler kartta yazılır). Hiç uyan yoksa en yakın 4 tarif gösterilir.
3. Tuz, su, sıvı yağ ve baharatlar varsayılan olarak "evde var" sayılır; panel üstündeki kutucukla kapatılabilir.
4. Seçim tarayıcıda saklanır (localStorage); tarif detay sayfasında "dolabına göre eksik: …" notu çıkar.

Yeni bir malzeme tanıtmak için `ingredients.py` içindeki `_CATALOG_ROWS` listesine, besin değerini de `nutrition.py` içindeki `FOODS` sözlüğüne ekleyip şunu çalıştırın (siteye istek atmaz):

```bash
cd backend && python main.py --retag
```

### Makro hesapla (`/makro`)

"Günlük Makro Besin İhtiyacı Hesaplama Aracı": cinsiyet, aktivite düzeyi, hedef (kilo vermek / korumak / kilo almak / kas yapmak), yaş, boy ve kilo girilir.

**Hesaplama**

| Adım | Formül |
|---|---|
| Bazal metabolizma (BMR) | Mifflin-St Jeor: 10 × kilo + 6,25 × boy − 5 × yaş + 5 (erkek) / −161 (kadın) |
| Günlük harcama | BMR × aktivite katsayısı (1,2 / 1,375 / 1,55 / 1,725 / 1,9) |
| Hedef kalori | kilo vermek ×0,8 · korumak ×1,0 · kilo almak ×1,15 · kas yapmak ×1,1 (alt sınır kadın 1200, erkek 1500 kcal) |
| Protein | kg başına 1,8 / 1,4 / 1,6 / 2,0 g (en fazla kalorinin %35'i) |
| Yağ | kalorinin %25 (kilo verme, kas) ya da %30'u |
| Karbonhidrat | kalan kalori ÷ 4 |
| Öğün hedefi | günlük kalorinin %30'u |

**Tarif önerisi**: her tarif için öğün hedefini tutturacak porsiyon (0,5 – 2) hesaplanır; tarifler bu porsiyonla
öğün kalorisine yakınlık, protein oranı ve yağ oranına göre puanlanır. Kas yapma ve kilo vermede protein ağırlığı
daha yüksektir. İlk 12 tarif gösterilir, kategoriye göre süzülebilir.

**Paylaş** form değerlerini bağlantıya ekler (`/makro?c=kadin&a=1.55&h=ver&y=32&b=172&k=69`); bağlantı açıldığında
sonuç otomatik hesaplanır. **Sitene Ekle** bir `<iframe>` kodu verir; `?embed=1` ile açılan sayfada üst menü ve
alt bilgi gizlenir, tarif kartları yeni sekmede açılır.

**Besin değerleri tahminidir.** Kaynak site kalori/makro vermediği için `backend/utils/nutrition.py` her malzeme
satırının miktarını okur ("1 su bardağı un" → 200 ml × 0,55 g/ml = 110 g), 100 g başına besin tablosuyla çarpar ve
porsiyon sayısına böler. Ev ölçüleri nedeniyle sonuç ±%20-30 sapabilir; arayüzde bu açıkça belirtilir. Kaynakta
porsiyon sayısı gerçekçi değilse (porsiyon başı 1200 kcal üstü) porsiyon 600 kcal'lik dilimlere göre yeniden
ölçeklenir ve `servings_adjusted: true` yazılır. Araç tıbbi tavsiye değildir.

## Proje yapısı

```
backend/
  main.py              giriş noktası, argparse, özet rapor, örnek kullanım
  config.py            ayarlar, SELECTORS, kategori URL'leri
  models/recipe.py     Recipe ve RecipeCollection sınıfları
  services/scraper.py  RecipeScraper (oturum, retry, robots.txt, link toplama, parse)
  utils/helpers.py     build_image_url, slugify, clean_text ve süre/porsiyon yardımcıları
  utils/ingredients.py malzeme kataloğu ve satırdan malzeme adı çıkarma (ingredient_tags)
  utils/nutrition.py   miktar/birim okuma ve porsiyon başına tahmini kalori-makro (nutrition)
  output/              recipes.json, recipes.csv
```

## Parse stratejisi

1. **JSON-LD**: `<script type="application/ld+json">` içinde `@type: "Recipe"` aranır (doğrudan, liste ya da `@graph` içinde).
2. **HTML (yedek)**: JSON-LD yoksa ya da alanları eksikse `config.SELECTORS` ile okunur.

Not: 2026-10-06 itibarıyla site JSON-LD'de Recipe bloğu **yayınlamıyor**; tarif verisi HTML içinde schema.org
*microdata* (`itemprop="recipeIngredient"` vb.) olarak duruyor. Bu yüzden şu an tüm tarifler HTML katmanından okunuyor
ve log'da `Parse yöntemi: html` görünüyor. Selector'lar bu `itemprop` niteliklerini hedeflediği için CSS sınıf adı
değişikliklerine karşı oldukça dayanıklıdır. Site ileride JSON-LD eklerse kod değişikliği gerekmeden o katman devreye girer.

## recipes.json'ın frontend'de kullanımı

Dosyanın kökünde iki alan var: `meta` ve `recipes`.

- `meta.total` toplam tarif sayısıdır, `meta.scraped_at` verinin ne zaman çekildiğini gösterir ("son güncelleme" bilgisi için).
- `recipes` bir dizidir; liste/kart sayfası bu diziyi baştan sona dolaşarak her tarif için bir kart çizer.
  Kartta `title`, `image_url`, `servings`, `duration` ve `ingredient_count` gösterilebilir.
- Kullanıcı bir karta tıkladığında detay sayfasının adresi `slug` ile kurulur (örneğin "/tarif/mercimek-corbasi").
  Detay sayfası açıldığında `recipes` dizisinde `slug` değeri eşleşen kayıt bulunur. `slug` her kayıtta benzersizdir.
  Aynı amaçla `key` (recipe1, recipe2, ...) ya da sayısal `id` de kullanılabilir.
- Detay sayfasında `ingredients` dizisi madde madde listelenir; her eleman tek bir temizlenmiş malzemedir.
- `image_source` değeri `"stock"` ise görsel siteden bulunamamış ve yer tutucu atanmıştır; frontend bu durumda
  farklı bir stil ya da kendi yer tutucusunu gösterebilir.
- Filtreleme: süreye göre filtre için metin olan `duration` yerine sayı olan `duration_minutes` kullanılmalıdır
  (örneğin "30 dakikadan kısa" = 0'dan büyük ve 30'a eşit ya da küçük). `duration_minutes` değeri `0` ise süre bilinmiyor demektir.
  Kategoriye göre filtre için `category` alanı kullanılır.
- Hiçbir alan `null` değildir. Metin alanlarında veri yoksa `"Bilgi bulunamadı"` yazılır; frontend bu değeri
  gizleyebilir ya da "—" olarak gösterebilir.
- `source_url` her tarifin orijinal adresidir; detay sayfasında kaynak linki olarak gösterilmelidir.

- `ingredient_tags` tarifin standart malzeme adlarıdır (ör. `["mercimek", "soğan", "tuz"]`); "dolabımda ne var?" eşleştirmesi bununla yapılır.
  `meta.ingredients` ise tüm malzemelerin `name`, `group`, `staple` (evde genelde bulunur), `count` (kaç tarifte geçiyor) bilgisini içerir.

- `nutrition` porsiyon başına tahmini değerlerdir: `calories` (kcal), `protein`, `carbs`, `fat` (gram),
  `servings_used` (hesapta kullanılan kişi sayısı), `servings_adjusted`, `confidence` (miktarı okunabilen satır oranı, 0-1)
  ve her zaman `estimated: true`. CSV'de `calories`, `protein_g`, `carbs_g`, `fat_g` sütunları olarak yer alır.

Spesifikasyona ek olarak şu alanlar eklendi: `nutrition` (makro hesaplama için), `category`, `duration_minutes` (filtreleme için), `ingredient_tags` ve `meta.ingredients` (dolap eşleştirmesi için) ve benzersiz `slug` garantisi.

## Site yapısı değişirse ne güncellenir? (sadece `backend/config.py`)

| Belirti | Güncellenecek yer |
|---|---|
| "0 tarif linki bulundu" / kategori sayfası boş | `SELECTORS["recipe_links"]` (şu an `div.recipe-cards` içindeki görsel ve başlık linkleri) |
| Kategori adresi 404 veriyor | `CATEGORIES` sözlüğündeki URL |
| Sayfa 2'den sonrası gelmiyor | `PAGINATION_PATTERN` (şu an `page/{page}/`; `?page=N` yapısına geçerse `"?page={page}"`) |
| Başlık "Bilgi bulunamadı" geliyor, tarifler atlanıyor | `SELECTORS["title"]` (şu an `h1.recipe-name`) |
| "Zorunlu alan eksik (ingredients)" uyarısı | `SELECTORS["ingredients"]` |
| Stok görsel sayısı artıyor | `SELECTORS["image"]` ve lazy-load nitelikleri için `IMAGE_ATTRIBUTES` |
| Porsiyon "Bilgi bulunamadı" | `SELECTORS["servings"]` (şu an `ul.short-info` ilk `li`) |
| Süre "Bilgi bulunamadı" | `SELECTORS["duration"]` (microdata) ve `SELECTORS["duration_text"]` (düz metin yedeği) |
| Video sayfaları ya da yeni bir tarif-dışı link tipi listeye karışıyor | `EXCLUDED_LINK_PATTERNS` |

Hangi selector'un bozulduğunu görmek için `python main.py --limit 3 --verbose` çalıştırın; her alan için okuma hataları DEBUG seviyesinde loglanır.

## Önemli notlar

- **robots.txt**: Kazıyıcı her istekten önce robots.txt'yi kontrol eder ve yasaklanan yolları istemez.
  Kategori ve tarif sayfaları genel kurallar altında serbesttir. Ancak site robots.txt'de
  `Content-Signal: ai-train=no, ai-input=no` bildiriyor ve bilinen veri toplama botlarını engelliyor.
- **Telif hakkı**: Tarif metinleri ve fotoğraflar site ile tarif sahiplerine aittir. Ödev ya da kişisel kullanım dışında,
  herkese açık bir sitede yayınlamadan önce nefisyemektarifleri.com'dan izin alın ve her tarifte `source_url` ile kaynak gösterin.
  Görselleri kendi sitenizden onların sunucusuna doğrudan bağlamak (hotlink) da ayrıca sorun yaratabilir.
- **Stok görsel**: `source.unsplash.com` servisi Unsplash tarafından kapatıldı ve şu an HTTP 503 dönüyor.
  Yayına almadan önce `config.STOCK_IMAGE_URL_TEMPLATE` değerini kendi yer tutucu görselinizle değiştirin.
  (Mevcut çalıştırmada 15 tarifin 15'inde de görsel siteden bulunduğu için bu yedek devreye girmedi.)

## Lisans

Kaynak kod MIT lisanslıdır, bkz. [LICENSE](../LICENSE). Çağlar Sapmaz tarafından yapıldı.
Tarif içerikleri ve görseller bu lisansın kapsamında değildir; nefisyemektarifleri.com ve
tarif sahiplerine aittir.
