/*
 * Kategori dairelerindeki çizim tarzı ikonlar (satır içi SVG).
 * Tüm ikonlar 64x64 viewBox kullanır; renkler CSS değişkenleriyle uyumludur.
 */
(function () {
  "use strict";

  const S = 'fill="none" stroke="#6e4a35" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"';
  const O = "#e9a46a";   // turuncu dolgu
  const L = "#f7d9bd";   // açık dolgu
  const W = "#ffffff";

  const svg = (body) =>
    `<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false">${body}</svg>`;

  const ICONS = {
    // Çorba: kase + buhar + kaşık
    corba: svg(`
      <path d="M24 10c-2 3 2 5 0 8M32 8c-2 3 2 5 0 8M40 10c-2 3 2 5 0 8" ${S}/>
      <path d="M44 24 54 14" ${S}/>
      <path d="M9 30h46a23 18 0 0 1-46 0z" fill="${O}" ${S.replace('fill="none" ', "")}/>
      <path d="M9 30h46" ${S}/>
      <path d="M14 34c6 2 30 2 36 0" stroke="${L}" stroke-width="2.4" fill="none" stroke-linecap="round"/>
      <path d="M24 47h16v4H24z" fill="${L}" ${S.replace('fill="none" ', "")}/>`),

    // Et: but
    et: svg(`
      <path d="m31 33-12 12" stroke="#6e4a35" stroke-width="8.5" stroke-linecap="round"/>
      <path d="m31 33-12 12" stroke="${W}" stroke-width="4" stroke-linecap="round"/>
      <circle cx="14.5" cy="45" r="4" fill="${W}" ${S.replace('fill="none" ', "")}/>
      <circle cx="19" cy="49.5" r="4" fill="${W}" ${S.replace('fill="none" ', "")}/>
      <path d="m16 47 4-4" stroke="${W}" stroke-width="4" stroke-linecap="round"/>
      <path d="M29 36c-7-7-6-19 3-24 9-5 20 0 22 9 2 10-6 18-16 18-4 0-7-1-9-3z" fill="${O}" ${S.replace('fill="none" ', "")}/>
      <path d="M38 17c5 0 9 3 10 8" stroke="${L}" stroke-width="2.4" fill="none" stroke-linecap="round"/>`),

    // Sebze: havuç
    sebze: svg(`
      <path d="M44 15c-2-5 0-9 4-11M47 17c3-4 8-5 12-3M46 16c1-5 5-8 9-8" ${S}/>
      <path d="M37 17c6-3 12 3 9 9L18 55c-3 3-8-1-5-5z" fill="${O}" ${S.replace('fill="none" ', "")}/>
      <path d="m27 32 5 4M22 40l4 3M33 25l4 3" ${S}/>`),

    // Makarna: kase + erişte + çubuklar
    makarna: svg(`
      <path d="M34 22 56 8M38 24l20-10" ${S}/>
      <path d="M14 30c2-8 6-10 8-4 2-8 6-8 8-2 2-6 6-6 8 0 2-6 6-4 8 2" ${S}/>
      <path d="M8 30h48a24 20 0 0 1-48 0z" fill="${O}" ${S.replace('fill="none" ', "")}/>
      <path d="M8 30h48" ${S}/>
      <path d="M24 48h16v5H24z" fill="${L}" ${S.replace('fill="none" ', "")}/>`),

    // Pilav: kase + pirinç tepesi
    pilav: svg(`
      <path d="M12 30c2-12 12-18 20-18s18 6 20 18" fill="${W}" ${S.replace('fill="none" ', "")}/>
      <path d="M22 20h2M30 16h2M38 20h2M26 26h2M34 24h2M42 27h2M18 27h2" ${S}/>
      <path d="M8 30h48a24 20 0 0 1-48 0z" fill="${O}" ${S.replace('fill="none" ', "")}/>
      <path d="M8 30h48" ${S}/>
      <path d="M24 48h16v5H24z" fill="${L}" ${S.replace('fill="none" ', "")}/>`),

    // Bakliyat: kavanoz + taneler
    bakliyat: svg(`
      <rect x="18" y="8" width="28" height="7" rx="2" fill="${O}" ${S.replace('fill="none" ', "")}/>
      <path d="M20 15h24c3 4 4 7 4 12v20c0 5-3 9-9 9H25c-6 0-9-4-9-9V27c0-5 1-8 4-12z" fill="${W}" ${S.replace('fill="none" ', "")}/>
      <ellipse cx="25" cy="34" rx="3.5" ry="2.5" fill="${O}" ${S.replace('fill="none" ', "")}/>
      <ellipse cx="35" cy="31" rx="3.5" ry="2.5" fill="${O}" ${S.replace('fill="none" ', "")}/>
      <ellipse cx="40" cy="41" rx="3.5" ry="2.5" fill="${O}" ${S.replace('fill="none" ', "")}/>
      <ellipse cx="29" cy="44" rx="3.5" ry="2.5" fill="${O}" ${S.replace('fill="none" ', "")}/>
      <ellipse cx="31" cy="38" rx="3.5" ry="2.5" fill="${L}" ${S.replace('fill="none" ', "")}/>`),

    // Salata: kase + yapraklar + domates
    salata: svg(`
      <path d="M16 30c-2-8 4-14 10-12 0-6 8-9 12-4 5-4 12 0 11 6 5 1 6 6 4 10" fill="${L}" ${S.replace('fill="none" ', "")}/>
      <circle cx="24" cy="25" r="5" fill="${O}" ${S.replace('fill="none" ', "")}/>
      <path d="M34 18c2 4 2 8 0 12M44 22c-2 3-2 6 0 8" ${S}/>
      <path d="M8 30h48a24 20 0 0 1-48 0z" fill="${W}" ${S.replace('fill="none" ', "")}/>
      <path d="M8 30h48" ${S}/>
      <path d="M14 36c8 3 28 3 36 0" stroke="${O}" stroke-width="2.4" fill="none" stroke-linecap="round"/>`),

    // Hamur işi: kruvasan
    hamurisi: svg(`
      <path d="M22 22c6-6 14-6 20 0l-4 20c-4 2-8 2-12 0z" fill="${O}" ${S.replace('fill="none" ', "")}/>
      <path d="M22 22 12 28c-4 3-3 8 0 12l14 2M42 22l10 6c4 3 3 8 0 12l-14 2" fill="${L}" ${S.replace('fill="none" ', "")}/>
      <path d="M12 40c-3 3-3 6 0 8l8-2M52 40c3 3 3 6 0 8l-8-2" ${S}/>
      <path d="m28 26 2 14M36 26l-2 14" ${S}/>`),

    // Tatlı: cupcake
    tatli: svg(`
      <circle cx="32" cy="10" r="3.5" fill="#c85a4a" stroke="#6e4a35" stroke-width="2.4"/>
      <path d="M16 32c-4 0-6-4-3-7 0-5 5-7 8-5 1-6 7-9 11-6 4-3 10 0 11 6 3-2 8 0 8 5 3 3 1 7-3 7z" fill="${L}" ${S.replace('fill="none" ', "")}/>
      <path d="M22 22c4 2 8 2 10-1M34 23c4 2 7 1 9-1" ${S}/>
      <path d="M15 32h34l-5 24H20z" fill="${O}" ${S.replace('fill="none" ', "")}/>
      <path d="m24 32 2 24M32 32v24M40 32l-2 24" ${S}/>`),

    // Kahvaltı: tabakta sahanda yumurta
    kahvalti: svg(`
      <ellipse cx="32" cy="38" rx="26" ry="16" fill="${W}" ${S.replace('fill="none" ', "")}/>
      <ellipse cx="32" cy="38" rx="18" ry="10" fill="none" stroke="${L}" stroke-width="2.4"/>
      <path d="M20 34c-2-6 4-10 9-8 3-4 11-3 12 2 5 0 7 6 3 9 1 5-6 7-10 4-4 3-12 2-12-2-3 0-4-3-2-5z" fill="${W}" ${S.replace('fill="none" ', "")}/>
      <circle cx="32" cy="35" r="5" fill="${O}" ${S.replace('fill="none" ', "")}/>
      <path d="M10 18c4 0 6 3 6 6M48 12c4 0 6 3 6 6" ${S}/>`),

    // Hızlı (30 dk altı): kronometre
    hizli: svg(`
      <path d="M28 8h8M32 8v5M47 16l3-3" ${S}/>
      <circle cx="32" cy="36" r="21" fill="${L}" ${S.replace('fill="none" ', "")}/>
      <path d="M32 36V22a14 14 0 0 1 13 10z" fill="${O}"/>
      <path d="M32 36V24M32 36l7 5" ${S}/>
      <circle cx="32" cy="36" r="2" fill="#6e4a35"/>`),

    // Az malzemeli: liste
    az: svg(`
      <rect x="14" y="8" width="36" height="48" rx="4" fill="${W}" ${S.replace('fill="none" ', "")}/>
      <rect x="24" y="5" width="16" height="7" rx="2" fill="${O}" ${S.replace('fill="none" ', "")}/>
      <path d="m20 24 3 3 5-6M20 36l3 3 5-6M20 48l3 3 5-6" ${S}/>
      <path d="M33 25h11M33 37h11M33 49h7" ${S}/>`),

    // Dolabımda ne var: buzdolabı
    dolap: svg(`
      <rect x="15" y="5" width="34" height="54" rx="6" fill="${W}" ${S.replace('fill="none" ', "")}/>
      <path d="M15 24h34" ${S}/>
      <path d="M21 12v6M21 30v10" ${S}/>
      <circle cx="40" cy="14" r="4" fill="${O}" ${S.replace('fill="none" ', "")}/>
      <rect x="29" y="34" width="14" height="16" rx="3" fill="${L}" ${S.replace('fill="none" ', "")}/>
      <path d="M33 34v-3h6v3" ${S}/>`),

    // Makro hesapla: pasta grafik
    makro: svg(`
      <circle cx="30" cy="34" r="22" fill="${L}" ${S.replace('fill="none" ', "")}/>
      <path d="M30 34V12a22 22 0 0 1 21 15z" fill="${O}" ${S.replace('fill="none" ', "")}/>
      <path d="M30 34 51 27a22 22 0 0 1-12 27z" fill="${W}" ${S.replace('fill="none" ', "")}/>
      <path d="M44 6v10M48 6v10M46 16v8" ${S}/>`),

    // Tümü: tabak + çatal bıçak
    tumu: svg(`
      <circle cx="32" cy="32" r="17" fill="${L}" ${S.replace('fill="none" ', "")}/>
      <circle cx="32" cy="32" r="10" fill="${O}" ${S.replace('fill="none" ', "")}/>
      <path d="M8 12v12a3 3 0 0 0 6 0V12M11 12v40M56 12c-4 2-5 8-5 14h5M56 12v40" ${S}/>`),
  };

  // Meta ikonları (detay sayfası) — currentColor kullanır.
  const M = 'fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"';
  const META = {
    servings: `<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="9" cy="8" r="3.2" ${M}/><path d="M3 20c0-3.5 2.7-6 6-6s6 2.5 6 6" ${M}/><circle cx="17" cy="9" r="2.5" ${M}/><path d="M16 14.2c3 .2 5 2.5 5 5.8" ${M}/></svg>`,
    duration: `<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="13" r="8" ${M}/><path d="M12 9v4l3 2M10 3h4" ${M}/></svg>`,
    ingredients: `<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="4" width="14" height="17" rx="2" ${M}/><path d="M9 9h6M9 13h6M9 17h3" ${M}/></svg>`,
  };

  // JSON'daki kategori adı -> ikon anahtarı
  const CATEGORY_ICON = {
    "Çorba Tarifleri": "corba",
    "Et Yemekleri": "et",
    "Sebze Yemekleri": "sebze",
    "Makarna Tarifleri": "makarna",
    "Pilav Tarifleri": "pilav",
    "Bakliyat Yemekleri": "bakliyat",
    "Salata, Meze, Kanepe": "salata",
    "Hamur İşi Tarifleri": "hamurisi",
    "Tatlı Tarifleri": "tatli",
    "Kahvaltılık Tarifler": "kahvalti",
  };

  window.RecipeIcons = {
    get(key) { return ICONS[key] || ICONS.tumu; },
    forCategory(name) { return ICONS[CATEGORY_ICON[name]] || ICONS.tumu; },
    meta: META,
  };
})();
