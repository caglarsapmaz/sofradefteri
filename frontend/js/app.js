/*
 * sofra defteri — tarif dizini
 *
 * Tek veri kaynağı backend'in ürettiği recipes.json dosyasıdır.
 * Yönlendirme History API ile yapılır (temiz adresler, sayfa yenilenmez):
 *   /                      -> tarif dizini (filtre + ızgara + sayfalama)
 *   /tarif/<slug>          -> tarif detayı
 *   /dolabim, /makro       -> dolabımda ne var?, makro hesaplama
 *   /hakkinda, /iletisim   -> basit sayfalar
 * Bu adreslere doğrudan girildiğinde Vercel'de vercel.json, yerelde serve.py
 * isteği frontend/index.html'e yönlendirir.
 */
(function () {
  "use strict";

  // ------------------------------------------------------------------ //
  // Ayarlar
  // ------------------------------------------------------------------ //
  const DATA_URL = "/backend/output/recipes.json";
  const PAGE_SIZE = 12;
  const MISSING = "Bilgi bulunamadı";
  const QUICK_MINUTES = 30;
  const FEW_INGREDIENTS = 8;

  // Kategorilerin karusel ve filtre listesindeki sırası.
  const CATEGORY_ORDER = [
    "Çorba Tarifleri", "Et Yemekleri", "Sebze Yemekleri", "Makarna Tarifleri",
    "Pilav Tarifleri", "Bakliyat Yemekleri", "Salata, Meze, Kanepe",
    "Hamur İşi Tarifleri", "Tatlı Tarifleri", "Kahvaltılık Tarifler",
  ];

  // ------------------------------------------------------------------ //
  // Durum
  // ------------------------------------------------------------------ //
  const state = {
    recipes: [],
    meta: null,
    bySlug: new Map(),
    groups: [],
    selected: { cat: new Set(), dur: new Set(), ing: new Set(), srv: new Set() },
    query: "",
    page: 1,
    indexScroll: 0,
    currentView: "index",
    // Dolabımda ne var?
    catalog: [],
    catalogByName: new Map(),
    ingredientGroups: [],
    pantry: new Set(),
    assumeStaples: true,
    pantryQuery: "",
    macroForm: null,
  };

  // ------------------------------------------------------------------ //
  // DOM
  // ------------------------------------------------------------------ //
  const $ = (sel, root = document) => root.querySelector(sel);
  const els = {
    viewIndex: $("#view-index"),
    viewDetail: $("#view-detail"),
    viewPage: $("#view-page"),
    viewPantry: $("#view-pantry"),
    viewMacro: $("#view-macro"),
    catTrack: $("#cat-track"),
    prev: $(".carousel-arrow.prev"),
    next: $(".carousel-arrow.next"),
    filters: $("#filters"),
    filterToggle: $(".filter-toggle"),
    filterBadge: $("#filter-badge"),
    grid: $("#recipe-grid"),
    pagination: $("#pagination"),
    resultInfo: $("#result-info"),
    searchToggle: $(".search-toggle"),
    searchBar: $("#search-bar"),
    searchInput: $("#search-input"),
    navToggle: $(".nav-toggle"),
    nav: $("#main-nav"),
    footerCats: $("#footer-cats"),
    footerStrip: $("#footer-strip"),
    newsletter: $("#newsletter"),
  };

  // ------------------------------------------------------------------ //
  // Yardımcılar
  // ------------------------------------------------------------------ //
  const ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  // Veri dış bir siteden kazındığı için ekrana basılan HER metin kaçışlanır.
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ESC[c]);
  const lower = (v) => String(v ?? "").toLocaleLowerCase("tr");
  const safeUrl = (u) => (/^https?:\/\//i.test(u || "") ? u : "");
  const has = (v) => v && v !== MISSING;

  function servingsLow(r) {
    const m = String(r.servings || "").match(/\d+/);
    return m ? Number(m[0]) : 0;
  }

  function categoryLabel(name) {
    return lower(name).replace(" tarifleri", "");
  }

  function formatDate(iso) {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "";
    return d.toLocaleDateString("tr-TR", { day: "numeric", month: "long", year: "numeric" }).toLocaleLowerCase("tr");
  }

  function imageHtml(r, cls = "", eager = false) {
    const url = r.image_source === "stock" ? "" : safeUrl(r.image_url);
    if (!url) return fallbackHtml(r);
    return `<img class="${cls}" src="${esc(url)}" alt="${esc(r.title)}" ${eager ? "" : 'loading="lazy"'} decoding="async" referrerpolicy="no-referrer" data-cat="${esc(r.category)}">`;
  }

  function fallbackHtml(r) {
    return `<div class="img-fallback" role="img" aria-label="${esc(r.title)}">${window.RecipeIcons.forCategory(r.category)}</div>`;
  }

  // ------------------------------------------------------------------ //
  // Filtre tanımları
  // ------------------------------------------------------------------ //
  function buildGroups() {
    const present = new Set(state.recipes.map((r) => r.category).filter(has));
    const cats = [
      ...CATEGORY_ORDER.filter((c) => present.has(c)),
      ...[...present].filter((c) => !CATEGORY_ORDER.includes(c)).sort((a, b) => a.localeCompare(b, "tr")),
    ];
    return [
      {
        id: "cat",
        legend: "kategoriye göre:",
        options: cats.map((c) => ({ value: c, label: categoryLabel(c), test: (r) => r.category === c })),
      },
      {
        id: "dur",
        legend: "süreye göre:",
        options: [
          { value: "30", label: `${QUICK_MINUTES} dk ve altı`, test: (r) => r.duration_minutes > 0 && r.duration_minutes <= QUICK_MINUTES },
          { value: "60", label: "31 – 60 dk", test: (r) => r.duration_minutes > 30 && r.duration_minutes <= 60 },
          { value: "61", label: "1 saatten uzun", test: (r) => r.duration_minutes > 60 },
        ],
      },
      {
        id: "ing",
        legend: "malzeme sayısına göre:",
        options: [
          { value: "8", label: `${FEW_INGREDIENTS} ve altı`, test: (r) => r.ingredient_count <= FEW_INGREDIENTS },
          { value: "12", label: "9 – 12 malzeme", test: (r) => r.ingredient_count > 8 && r.ingredient_count <= 12 },
          { value: "13", label: "13 ve üzeri", test: (r) => r.ingredient_count > 12 },
        ],
      },
      {
        id: "srv",
        legend: "kişi sayısına göre:",
        options: [
          { value: "4", label: "1 – 4 kişilik", test: (r) => servingsLow(r) > 0 && servingsLow(r) <= 4 },
          { value: "8", label: "5 – 8 kişilik", test: (r) => servingsLow(r) > 4 && servingsLow(r) <= 8 },
          { value: "9", label: "8 kişiden fazla", test: (r) => servingsLow(r) > 8 },
        ],
      },
    ];
  }

  function matchesQuery(r) {
    if (!state.query) return true;
    const q = lower(state.query);
    return lower(r.title).includes(q) || r.ingredients.some((i) => lower(i).includes(q));
  }

  // Grup içinde VEYA, gruplar arasında VE mantığı. `skipGroup` faset sayımı için.
  function filterRecipes(skipGroup = null) {
    return state.recipes.filter((r) => {
      if (!matchesQuery(r)) return false;
      for (const g of state.groups) {
        if (g.id === skipGroup) continue;
        const sel = state.selected[g.id];
        if (!sel.size) continue;
        if (!g.options.some((o) => sel.has(o.value) && o.test(r))) return false;
      }
      return true;
    });
  }

  function activeFilterCount() {
    return Object.values(state.selected).reduce((n, s) => n + s.size, 0);
  }

  function clearFilters() {
    Object.values(state.selected).forEach((s) => s.clear());
    state.query = "";
    els.searchInput.value = "";
    state.page = 1;
  }

  // ------------------------------------------------------------------ //
  // Kategori karuseli
  // ------------------------------------------------------------------ //
  function carouselItems() {
    const items = [
      { key: "all", label: "tümü", icon: window.RecipeIcons.get("tumu") },
      { key: "pantry", label: "dolabımda ne var?", icon: window.RecipeIcons.get("dolap") },
      { key: "macro", label: "makro hesapla", icon: window.RecipeIcons.get("makro") },
    ];
    state.groups[0].options.forEach((o) =>
      items.push({ key: `cat:${o.value}`, label: o.label, icon: window.RecipeIcons.forCategory(o.value) })
    );
    items.push({ key: "dur:30", label: `${QUICK_MINUTES} dk tarifleri`, icon: window.RecipeIcons.get("hizli") });
    items.push({ key: "ing:8", label: `< ${FEW_INGREDIENTS + 1} malzeme`, icon: window.RecipeIcons.get("az") });
    return items;
  }

  function isOnly(groupId, value) {
    const others = Object.entries(state.selected).every(([id, s]) => id === groupId || s.size === 0);
    const s = state.selected[groupId];
    return others && s.size === 1 && s.has(value);
  }

  function isCarouselActive(key) {
    if (key === "all") return activeFilterCount() === 0;
    if (key === "pantry" || key === "macro") return false;
    const [g, v] = [key.slice(0, key.indexOf(":")), key.slice(key.indexOf(":") + 1)];
    return isOnly(g, v);
  }

  function renderCarousel() {
    els.catTrack.innerHTML = carouselItems()
      .map(
        (it) => `<li><button type="button" class="cat-item${isCarouselActive(it.key) ? " is-active" : ""}" data-key="${esc(it.key)}" aria-pressed="${isCarouselActive(it.key)}">
          <span class="cat-circle">${it.icon}</span>
          <span class="cat-label">${esc(it.label)}</span>
        </button></li>`
      )
      .join("");
    updateArrows();
  }

  function onCarouselClick(e) {
    const btn = e.target.closest(".cat-item");
    if (!btn) return;
    const key = btn.dataset.key;
    if (key === "pantry" || key === "macro") {
      navigate(key === "pantry" ? "/dolabim" : "/makro");
      return;
    }
    const wasActive = isCarouselActive(key);
    Object.values(state.selected).forEach((s) => s.clear());
    if (key !== "all" && !wasActive) {
      const i = key.indexOf(":");
      state.selected[key.slice(0, i)].add(key.slice(i + 1));
    }
    state.page = 1;
    renderIndex();
  }

  function updateArrows() {
    const t = els.catTrack;
    els.prev.disabled = t.scrollLeft <= 2;
    els.next.disabled = t.scrollLeft + t.clientWidth >= t.scrollWidth - 2;
  }

  // ------------------------------------------------------------------ //
  // Filtre paneli
  // ------------------------------------------------------------------ //
  function renderFilters() {
    const html = state.groups
      .map((g) => {
        const base = filterRecipes(g.id);
        const opts = g.options
          .map((o) => {
            const count = base.filter(o.test).length;
            const checked = state.selected[g.id].has(o.value);
            const disabled = !checked && count === 0;
            return `<label class="filter-option">
              <input type="checkbox" data-group="${g.id}" value="${esc(o.value)}"${checked ? " checked" : ""}${disabled ? " disabled" : ""}>
              <span>${esc(o.label)} <span class="count">(${count})</span></span>
            </label>`;
          })
          .join("");
        return `<fieldset class="filter-group"><legend>${esc(g.legend)}</legend>${opts}</fieldset>`;
      })
      .join("");
    const clear = activeFilterCount()
      ? `<div class="filter-actions"><button type="button" class="filter-clear" data-action="clear">filtreleri temizle</button></div>`
      : "";
    els.filters.innerHTML = html + clear;

    const n = activeFilterCount();
    els.filterBadge.hidden = n === 0;
    els.filterBadge.textContent = n;
  }

  function onFilterChange(e) {
    const input = e.target.closest('input[type="checkbox"][data-group]');
    if (!input) return;
    const set = state.selected[input.dataset.group];
    input.checked ? set.add(input.value) : set.delete(input.value);
    state.page = 1;
    renderIndex();
  }

  // ------------------------------------------------------------------ //
  // Izgara + sayfalama
  // ------------------------------------------------------------------ //
  function cardHtml(r) {
    const badge = r.duration_minutes > 0 ? `<span class="card-badge">${esc(r.duration)}</span>` : "";
    return `<li><a class="recipe-card" href="/tarif/${encodeURIComponent(r.slug)}">
      <div class="card-media">${imageHtml(r)}${badge}</div>
      <h3 class="card-title">${esc(r.title)}</h3>
    </a></li>`;
  }

  function renderGrid(list) {
    const pages = Math.max(1, Math.ceil(list.length / PAGE_SIZE));
    state.page = Math.min(Math.max(1, state.page), pages);
    const slice = list.slice((state.page - 1) * PAGE_SIZE, state.page * PAGE_SIZE);

    els.grid.innerHTML = slice.length
      ? slice.map(cardHtml).join("")
      : `<li class="empty-state"><strong>bu filtrelere uyan tarif yok</strong>
           birkaç filtreyi kaldırmayı deneyin. <button type="button" class="filter-clear" data-action="clear">filtreleri temizle</button></li>`;

    renderPagination(pages);

    const parts = [`${list.length} tarif`];
    if (state.query) parts.unshift(`“${esc(state.query)}” için`);
    const showClear = activeFilterCount() || state.query;
    els.resultInfo.innerHTML =
      parts.join(" ") +
      (pages > 1 ? ` · sayfa ${state.page}/${pages}` : "") +
      (showClear ? ` · <button type="button" data-action="clear">temizle</button>` : "");
  }

  function pageList(pages, current) {
    if (pages <= 14) return Array.from({ length: pages }, (_, i) => i + 1);
    const set = new Set([1, 2, pages - 1, pages, current - 1, current, current + 1]);
    const arr = [...set].filter((p) => p >= 1 && p <= pages).sort((a, b) => a - b);
    const out = [];
    arr.forEach((p, i) => {
      if (i && p - arr[i - 1] > 1) out.push("…");
      out.push(p);
    });
    return out;
  }

  function renderPagination(pages) {
    if (pages <= 1) {
      els.pagination.innerHTML = "";
      return;
    }
    els.pagination.innerHTML = pageList(pages, state.page)
      .map((p) =>
        p === "…"
          ? `<span class="page-btn" aria-hidden="true">…</span>`
          : `<button type="button" class="page-btn" data-page="${p}"${p === state.page ? ' aria-current="page"' : ""} aria-label="sayfa ${p}">${p}</button>`
      )
      .join("");
  }

  function onPageClick(e) {
    const btn = e.target.closest("[data-page]");
    if (!btn) return;
    state.page = Number(btn.dataset.page);
    renderIndex();
    els.filters.scrollIntoView({ block: "start" });
    window.scrollBy(0, -16);
  }

  function renderIndex() {
    renderCarousel();
    renderFilters();
    renderGrid(filterRecipes());
  }

  // ------------------------------------------------------------------ //
  // Detay
  // ------------------------------------------------------------------ //
  function renderDetail(slug) {
    const r = state.bySlug.get(slug);
    if (!r) {
      els.viewDetail.innerHTML = `<div class="container simple-page">
        <h1 class="page-title">tarif bulunamadı</h1>
        <p>aradığınız tarif kaldırılmış ya da adresi değişmiş olabilir. <a href="/">tarif dizinine dön</a>.</p></div>`;
      document.title = "tarif bulunamadı · sofra defteri";
      return;
    }

    const related = state.recipes.filter((x) => x.category === r.category && x.slug !== r.slug);
    const fill = state.recipes.filter((x) => x.category !== r.category && x.slug !== r.slug);
    const relatedList = [...related, ...fill].slice(0, 4);

    const meta = [
      { icon: window.RecipeIcons.meta.servings, label: "porsiyon", value: has(r.servings) ? r.servings : "—" },
      { icon: window.RecipeIcons.meta.duration, label: "süre", value: has(r.duration) ? r.duration : "—" },
      { icon: window.RecipeIcons.meta.ingredients, label: "malzeme", value: `${r.ingredient_count} adet` },
    ];

    const source = safeUrl(r.source_url);
    els.viewDetail.innerHTML = `<article class="detail container">
      <nav class="breadcrumb" aria-label="konum">
        <a href="/">tarifler</a><span aria-hidden="true">/</span>
        ${has(r.category) ? `<a href="/" data-goto-cat="${esc(r.category)}">${esc(categoryLabel(r.category))}</a><span aria-hidden="true">/</span>` : ""}
        <span aria-current="page">${esc(lower(r.title))}</span>
      </nav>

      <div class="detail-grid">
        <div class="detail-media">${imageHtml(r, "", true)}</div>
        <div>
          ${has(r.category) ? `<a href="/" class="detail-cat" data-goto-cat="${esc(r.category)}">${esc(categoryLabel(r.category))}</a>` : ""}
          <h1 class="detail-title">${esc(r.title)}</h1>
          <div class="detail-meta">
            ${meta.map((m) => `<div class="meta-item">${m.icon}<span class="meta-label">${m.label}</span><span class="meta-value">${esc(m.value)}</span></div>`).join("")}
          </div>
          ${nutritionHtml(r)}
          ${pantryNoteHtml(r)}
          <div class="ing-head"><h2>malzemeler</h2><span>aldıklarınızı işaretleyin</span></div>
          <ul class="ing-list" role="list">
            ${r.ingredients.map((i) => `<li><label class="ing-item"><input type="checkbox"><span>${esc(i)}</span></label></li>`).join("")}
          </ul>
          ${source ? `<a class="btn-primary" href="${esc(source)}" target="_blank" rel="noopener">yapılışı için tarife git <span aria-hidden="true">↗</span></a>
          <p class="source-note">kaynak: nefisyemektarifleri.com</p>` : ""}
        </div>
      </div>

      ${relatedList.length ? `<section class="related" aria-labelledby="related-title">
        <h2 id="related-title">bunları da sevebilirsiniz</h2>
        <ul class="recipe-grid" role="list">${relatedList.map(cardHtml).join("")}</ul>
      </section>` : ""}
    </article>`;
    document.title = `${lower(r.title)} · sofra defteri`;
  }

  // ------------------------------------------------------------------ //
  // Basit sayfalar
  // ------------------------------------------------------------------ //
  const PAGES = {
    hakkinda: () => `<div class="simple-page">
      <h1 class="page-title">hakkında</h1>
      <p>sofra defteri, Türk mutfağından seçilmiş tarifleri tek bir yerde toplayan ve
      kategori, süre, malzeme sayısı ve kişi sayısına göre filtrelemenizi sağlayan bir tarif dizinidir.</p>
      <p>şu an <strong>${state.recipes.length}</strong> tarif listeleniyor. tüm tarif içerikleri ve görseller
      <a href="https://www.nefisyemektarifleri.com" target="_blank" rel="noopener">nefisyemektarifleri.com</a>
      ve tarif sahiplerine aittir; her tarifin detay sayfasında orijinal kaynağa bağlantı bulunur.</p>
      <p><a href="/">tarif dizinine dön →</a></p></div>`,
    iletisim: () => `<div class="simple-page">
      <h1 class="page-title">iletişim</h1>
      <p>öneri, tarif isteği ya da hata bildirimi için sayfanın altındaki “haberdar ol” formunu kullanabilirsiniz.</p>
      <p><a href="/">tarif dizinine dön →</a></p></div>`,
  };

  // ------------------------------------------------------------------ //
  // Yönlendirme
  // ------------------------------------------------------------------ //
  function setActiveNav(key) {
    document.querySelectorAll(".nav-link").forEach((a) => a.classList.toggle("is-active", a.dataset.nav === key));
  }

  function show(view) {
    if (state.currentView === "index" && view !== "index") state.indexScroll = window.scrollY;
    els.viewIndex.hidden = view !== "index";
    els.viewDetail.hidden = view !== "detail";
    els.viewPage.hidden = view !== "page";
    els.viewPantry.hidden = view !== "pantry";
    els.viewMacro.hidden = view !== "macro";
    state.currentView = view;
  }

  // Bu adresler uygulamanın kendi sayfalarıdır; tıklanınca sayfa yenilenmeden açılır.
  const APP_ROUTE = /^\/(?:|dolabim|makro|hakkinda|iletisim|tarif\/[^/]+)$/;

  // Uygulama içi geçiş: adresi History API ile değiştirir, sayfayı yeniden yüklemez.
  function navigate(url) {
    if (url !== location.pathname + location.search) history.pushState(null, "", url);
    route();
  }

  // Eski "#/makro?..." biçimli bağlantıları yeni temiz adrese çevirir (paylaşılmış linkler kırılmasın).
  function upgradeHashUrl() {
    if (!location.hash.startsWith("#/")) return;
    const [path, query = ""] = location.hash.slice(1).split("?");
    const params = new URLSearchParams(query);
    if (new URLSearchParams(location.search).get("embed") === "1") params.set("embed", "1");
    const qs = params.toString();
    history.replaceState(null, "", path + (qs ? `?${qs}` : ""));
  }

  function route() {
    const hash = decodeURIComponent(location.pathname).replace(/\/+$/, "") || "/";
    const query = location.search.slice(1);
    els.nav.classList.remove("is-open");
    els.navToggle.setAttribute("aria-expanded", "false");

    const detail = hash.match(/^\/tarif\/(.+)$/);
    if (detail) {
      show("detail");
      setActiveNav("recipes");
      renderDetail(detail[1]);
      window.scrollTo(0, 0);
      return;
    }
    if (hash === "/makro") {
      show("macro");
      setActiveNav("macro");
      document.title = "makro hesapla · sofra defteri";
      routeMacro(query);
      window.scrollTo(0, 0);
      return;
    }
    if (hash === "/dolabim") {
      show("pantry");
      setActiveNav("pantry");
      document.title = "dolabımda ne var? · sofra defteri";
      renderPantry();
      window.scrollTo(0, 0);
      return;
    }
    const page = hash.match(/^\/(hakkinda|iletisim)$/);
    if (page) {
      show("page");
      setActiveNav(page[1] === "hakkinda" ? "about" : "contact");
      els.viewPage.innerHTML = PAGES[page[1]]();
      document.title = `${page[1] === "hakkinda" ? "hakkında" : "iletişim"} · sofra defteri`;
      window.scrollTo(0, 0);
      return;
    }
    const wasIndex = state.currentView === "index";
    show("index");
    setActiveNav("recipes");
    document.title = "sofra defteri · tarif dizini";
    renderIndex();
    if (!wasIndex) requestAnimationFrame(() => window.scrollTo(0, state.indexScroll));
  }

  function gotoCategory(cat) {
    clearFilters();
    state.selected.cat.add(cat);
    if (state.currentView === "index") {
      renderIndex();
      els.viewIndex.scrollIntoView();
    } else {
      state.indexScroll = 0;
      navigate("/");
    }
  }

  // ------------------------------------------------------------------ //
  // Footer
  // ------------------------------------------------------------------ //
  function renderFooter() {
    const counts = new Map();
    state.recipes.forEach((r) => has(r.category) && counts.set(r.category, (counts.get(r.category) || 0) + 1));
    els.footerCats.innerHTML = [...counts.entries()]
      .sort((a, b) => b[1] - a[1] || CATEGORY_ORDER.indexOf(a[0]) - CATEGORY_ORDER.indexOf(b[0]))
      .slice(0, 3)
      .map(([c]) => `<li><a href="/" data-goto-cat="${esc(c)}">${esc(categoryLabel(c))}</a></li>`)
      .join("");

    const withImage = state.recipes.filter((r) => r.image_source !== "stock");
    const step = Math.max(1, Math.floor(withImage.length / 6));
    const strip = [];
    for (let i = 0; i < withImage.length && strip.length < 6; i += step) strip.push(withImage[i]);
    els.footerStrip.innerHTML = strip
      .map((r) => `<li><a href="/tarif/${encodeURIComponent(r.slug)}" aria-label="${esc(r.title)}">${imageHtml(r)}</a></li>`)
      .join("");

    $("#year").textContent = new Date().getFullYear();
    if (state.meta && state.meta.scraped_at) {
      $("#data-date").textContent = `veriler ${formatDate(state.meta.scraped_at)} tarihinde güncellendi.`;
    }
  }

  // ------------------------------------------------------------------ //
  // Olaylar
  // ------------------------------------------------------------------ //
  function bindEvents() {
    // Geri / ileri tuşları
    window.addEventListener("popstate", route);

    els.catTrack.addEventListener("click", onCarouselClick);
    els.catTrack.addEventListener("scroll", updateArrows, { passive: true });
    window.addEventListener("resize", updateArrows);
    els.prev.addEventListener("click", () => els.catTrack.scrollBy({ left: -els.catTrack.clientWidth * 0.8 }));
    els.next.addEventListener("click", () => els.catTrack.scrollBy({ left: els.catTrack.clientWidth * 0.8 }));

    els.filters.addEventListener("change", onFilterChange);
    bindPantryEvents();
    bindMacroEvents();
    els.pagination.addEventListener("click", onPageClick);

    document.addEventListener("click", (e) => {
      if (e.target.closest('[data-action="clear"]')) {
        clearFilters();
        renderIndex();
        return;
      }
      const goto = e.target.closest("[data-goto-cat]");
      if (goto) {
        e.preventDefault();
        gotoCategory(goto.dataset.gotoCat);
        return;
      }
      // Site içi bağlantılar: tam sayfa yüklemesi yerine History API ile geçiş.
      // Yeni sekme (cmd/ctrl tıklama, target) ve dosya bağlantıları tarayıcıya bırakılır.
      const link = e.target.closest("a[href]");
      if (!link || e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      if (link.target || link.hasAttribute("download") || link.origin !== location.origin) return;
      if (!APP_ROUTE.test(link.pathname)) return;
      e.preventDefault();
      navigate(link.pathname + link.search);
    });

    els.filterToggle.addEventListener("click", () => {
      const open = els.filters.classList.toggle("is-open");
      els.filterToggle.setAttribute("aria-expanded", String(open));
    });

    els.navToggle.addEventListener("click", () => {
      const open = els.nav.classList.toggle("is-open");
      els.navToggle.setAttribute("aria-expanded", String(open));
    });

    els.searchToggle.addEventListener("click", () => {
      const open = els.searchBar.hidden;
      els.searchBar.hidden = !open;
      els.searchToggle.setAttribute("aria-expanded", String(open));
      if (open) els.searchInput.focus();
    });

    let t;
    els.searchInput.addEventListener("input", () => {
      clearTimeout(t);
      t = setTimeout(() => {
        state.query = els.searchInput.value.trim();
        state.page = 1;
        if (state.currentView !== "index") {
          state.indexScroll = 0;
          navigate("/");
        } else {
          renderIndex();
        }
      }, 150);
    });
    els.searchInput.addEventListener("keydown", (e) => {
      if (e.key === "Escape") els.searchToggle.click();
    });

    // Kırık görsel -> kategori ikonlu yer tutucu (error olayı kabarcıklanmaz, capture gerekir).
    document.addEventListener(
      "error",
      (e) => {
        const img = e.target;
        if (!(img instanceof HTMLImageElement) || !img.dataset.cat) return;
        const div = document.createElement("div");
        div.className = "img-fallback";
        div.setAttribute("role", "img");
        div.setAttribute("aria-label", img.alt);
        div.innerHTML = window.RecipeIcons.forCategory(img.dataset.cat);
        img.replaceWith(div);
      },
      true
    );

    // Bülten formu: sunucu katmanı olmadığı için yalnızca doğrulama yapılır, veri gönderilmez.
    els.newsletter.addEventListener("submit", (e) => {
      e.preventDefault();
      const email = els.newsletter.elements.email;
      const msg = $(".newsletter-msg", els.newsletter);
      const ok = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value.trim());
      email.setAttribute("aria-invalid", String(!ok));
      if (!ok) {
        msg.textContent = "lütfen geçerli bir e-posta adresi yazın.";
        email.focus();
        return;
      }
      els.newsletter.reset();
      msg.textContent = "teşekkürler! bülten yakında başlıyor.";
    });
  }


  // ------------------------------------------------------------------ //
  // Dolabımda ne var?
  // Kullanıcının seçtiği malzemeler, her tarifin `ingredient_tags` listesiyle
  // karşılaştırılır. Tuz, su, sıvı yağ ve baharatlar (katalogda staple=true)
  // varsayılan olarak "evde var" sayılır.
  // ------------------------------------------------------------------ //
  const PANTRY_KEY = "sofra-defteri:dolap";
  const MAX_MISSING = 2;

  const isStaple = (name) => Boolean(state.catalogByName.get(name)?.staple);

  function loadPantry() {
    try {
      const saved = JSON.parse(localStorage.getItem(PANTRY_KEY) || "null");
      if (!saved) return;
      (saved.items || []).forEach((n) => state.catalogByName.has(n) && state.pantry.add(n));
      if (typeof saved.assumeStaples === "boolean") state.assumeStaples = saved.assumeStaples;
    } catch (_) {
      /* gizli pencere vb. durumlarda depolama kullanılamayabilir; seçim yalnızca bu oturumda kalır */
    }
  }

  function savePantry() {
    try {
      localStorage.setItem(PANTRY_KEY, JSON.stringify({ items: [...state.pantry], assumeStaples: state.assumeStaples }));
    } catch (_) {
      /* yoksay */
    }
  }

  function pantryMatch(r) {
    const required = r.ingredient_tags.filter((t) => !(state.assumeStaples && isStaple(t)));
    const missing = required.filter((t) => !state.pantry.has(t));
    return { r, required: required.length, matched: required.length - missing.length, missing };
  }

  function pantryResults() {
    const all = state.recipes
      .map(pantryMatch)
      .filter((m) => m.matched > 0)
      .sort((a, b) => a.missing.length - b.missing.length || b.matched - a.matched || a.required - b.required);
    return {
      ready: all.filter((m) => m.missing.length === 0),
      almost: all.filter((m) => m.missing.length > 0 && m.missing.length <= MAX_MISSING),
      closest: all.filter((m) => m.missing.length > MAX_MISSING).slice(0, 4),
    };
  }

  function chipHtml(item, { removable = false } = {}) {
    const on = state.pantry.has(item.name);
    if (removable) {
      return `<button type="button" class="chip is-on" data-ing="${esc(item.name)}" aria-label="${esc(item.name)} çıkar">${esc(item.name)} <span aria-hidden="true">×</span></button>`;
    }
    return `<button type="button" class="chip${on ? " is-on" : ""}" data-ing="${esc(item.name)}" aria-pressed="${on}">${esc(item.name)} <span class="chip-count">${item.count}</span></button>`;
  }

  function pantryCardHtml(m) {
    const r = m.r;
    const pct = m.required ? Math.round((m.matched / m.required) * 100) : 100;
    const status = m.missing.length
      ? `<p class="match-text">eksik: <strong>${m.missing.map(esc).join(", ")}</strong></p>`
      : `<p class="match-text is-ready">tüm malzemeler dolabında</p>`;
    return `<li><a class="recipe-card" href="/tarif/${encodeURIComponent(r.slug)}">
      <div class="card-media">${imageHtml(r)}<span class="card-badge">${m.matched}/${m.required} malzeme</span></div>
      <h3 class="card-title">${esc(r.title)}</h3>
      <div class="card-match">
        <div class="match-bar${m.missing.length ? "" : " is-ready"}" role="img" aria-label="malzemelerin yüzde ${pct}'i var"><span style="width:${pct}%"></span></div>
        ${status}
      </div>
    </a></li>`;
  }

  function renderPantryShell() {
    els.viewPantry.innerHTML = `<div class="container pantry">
      <h1 class="page-title">dolabımda ne var?</h1>
      <p class="pantry-lead">evdeki malzemeleri seç; hemen yapabileceğin tarifleri ve birkaç eksikle yapabileceklerini gösterelim.</p>
      <div class="pantry-layout">
        <aside class="pantry-panel" aria-label="malzeme seçimi">
          <label class="search-field">
            <span class="visually-hidden">malzeme ara</span>
            <input id="pantry-search" type="search" placeholder="malzeme ara… (ör. patates)" autocomplete="off">
          </label>
          <div id="pantry-selected" class="pantry-selected"></div>
          <label class="filter-option staple-toggle">
            <input type="checkbox" id="assume-staples"${state.assumeStaples ? " checked" : ""}>
            <span>tuz, su, sıvı yağ ve baharatlar evde var</span>
          </label>
          <div id="pantry-groups" class="pantry-groups"></div>
          <button type="button" id="pantry-jump" class="pantry-jump" hidden></button>
        </aside>
        <div id="pantry-results" class="pantry-results" aria-live="polite"></div>
      </div>
    </div>`;
    state.pantryQuery = "";
  }

  function renderPantryPanel() {
    const selected = [...state.pantry].map((n) => state.catalogByName.get(n)).filter(Boolean);
    $("#pantry-selected").innerHTML = selected.length
      ? `<div class="pantry-selected-head"><span>seçtiklerin (${selected.length})</span>
           <button type="button" class="filter-clear" data-pantry-clear>temizle</button></div>
         <div class="chip-list">${selected.map((i) => chipHtml(i, { removable: true })).join("")}</div>`
      : `<p class="pantry-hint">henüz malzeme seçmedin.</p>`;

    const q = lower(state.pantryQuery || "");
    const groups = state.ingredientGroups
      .filter((g) => !(state.assumeStaples && state.catalog.filter((i) => i.group === g).every((i) => i.staple)))
      .map((g) => {
        const items = state.catalog.filter(
          (i) => i.group === g && !(state.assumeStaples && i.staple) && (!q || lower(i.name).includes(q))
        );
        if (!items.length) return "";
        return `<fieldset class="filter-group pantry-group"><legend>${esc(g)}</legend>
          <div class="chip-list">${items.map((i) => chipHtml(i)).join("")}</div></fieldset>`;
      })
      .join("");
    $("#pantry-groups").innerHTML = groups || `<p class="pantry-hint">“${esc(state.pantryQuery)}” ile eşleşen malzeme yok.</p>`;
  }

  function renderPantryResults() {
    const box = $("#pantry-results");
    if (!state.catalog.length) {
      box.innerHTML = `<div class="empty-state"><strong>malzeme bilgisi bulunamadı</strong>
        recipes.json dosyasında <code>ingredient_tags</code> alanı yok. backend klasöründe
        <code>python main.py --retag</code> komutunu çalıştırın.</div>`;
      return;
    }
    if (!state.pantry.size) {
      $("#pantry-jump").hidden = true;
      const popular = state.catalog
        .filter((i) => !i.staple)
        .sort((a, b) => b.count - a.count)
        .slice(0, 10);
      box.innerHTML = `<div class="pantry-empty">
        <div class="cat-circle">${window.RecipeIcons.get("dolap")}</div>
        <strong>başlamak için malzeme seç</strong>
        <p>en çok kullanılanlardan hızlıca ekle:</p>
        <div class="chip-list">${popular.map((i) => chipHtml(i)).join("")}</div>
      </div>`;
      return;
    }

    const { ready, almost, closest } = pantryResults();
    const jump = $("#pantry-jump");
    const found = ready.length + almost.length;
    jump.hidden = false;
    jump.textContent = found ? `${found} tarifi gör ↓` : "en yakın tarifleri gör ↓";
    const section = (title, list, note = "") =>
      list.length
        ? `<section class="pantry-section"><h2>${title} <span>(${list.length})</span></h2>${note}
             <ul class="recipe-grid pantry-grid" role="list">${list.map(pantryCardHtml).join("")}</ul></section>`
        : "";

    let html =
      section("hemen yapabilirsin", ready) +
      section(`${MAX_MISSING} malzemeye kadar eksik`, almost);
    if (!ready.length && !almost.length) {
      html =
        `<div class="pantry-none"><strong>bu malzemelerle tam uyan tarif yok</strong>
          birkaç malzeme daha ekledikçe sonuçlar burada belirecek.</div>` +
        section("en yakın tarifler", closest);
    }
    box.innerHTML = html;
  }

  function renderPantry() {
    renderPantryShell();
    renderPantryPanel();
    renderPantryResults();
  }

  function refreshPantry() {
    savePantry();
    renderPantryPanel();
    renderPantryResults();
  }

  function bindPantryEvents() {
    els.viewPantry.addEventListener("click", (e) => {
      const chip = e.target.closest("[data-ing]");
      if (chip) {
        const name = chip.dataset.ing;
        state.pantry.has(name) ? state.pantry.delete(name) : state.pantry.add(name);
        refreshPantry();
        return;
      }
      if (e.target.closest("#pantry-jump")) {
        $("#pantry-results").scrollIntoView({ block: "start" });
        return;
      }
      if (e.target.closest("[data-pantry-clear]")) {
        state.pantry.clear();
        refreshPantry();
      }
    });
    els.viewPantry.addEventListener("change", (e) => {
      if (e.target.id === "assume-staples") {
        state.assumeStaples = e.target.checked;
        refreshPantry();
      }
    });
    els.viewPantry.addEventListener("input", (e) => {
      if (e.target.id === "pantry-search") {
        state.pantryQuery = e.target.value.trim();
        renderPantryPanel();
      }
    });
  }

  function pantryNoteHtml(r) {
    if (!state.pantry.size || !r.ingredient_tags.length) return "";
    const m = pantryMatch(r);
    const text = m.missing.length
      ? `dolabına göre eksik: <strong>${m.missing.map(esc).join(", ")}</strong>`
      : `<strong>bu tarifin tüm malzemeleri dolabında.</strong>`;
    return `<p class="pantry-note">${text} · <a href="/dolabim">dolabı düzenle</a></p>`;
  }


  // ------------------------------------------------------------------ //
  // Günlük makro besin ihtiyacı
  // BMR: Mifflin-St Jeor. Günlük ihtiyaç = BMR x aktivite katsayısı,
  // ardından hedefe göre kalori ayarı ve makro dağılımı yapılır.
  // Tarif besin değerleri backend'de malzemelerden TAHMİN edilmiştir.
  // ------------------------------------------------------------------ //
  const ACTIVITY = [
    { value: "1.2", label: "Hareketsiz (masa başı iş, egzersiz yok)" },
    { value: "1.375", label: "Az hareketli (haftada 1-3 gün hafif egzersiz)" },
    { value: "1.55", label: "Orta hareketli (haftada 3-5 gün egzersiz)" },
    { value: "1.725", label: "Çok hareketli (haftada 6-7 gün yoğun egzersiz)" },
    { value: "1.9", label: "Aşırı hareketli (fiziksel iş ya da günde 2 antrenman)" },
  ];
  const GOALS = {
    ver: { key: "ver", label: "Kilo vermek", factor: 0.8, proteinPerKg: 1.8, fatPct: 0.25, mealTarget: 0.9 },
    koru: { key: "koru", label: "Mevcut durumu korumak", factor: 1.0, proteinPerKg: 1.4, fatPct: 0.3, mealTarget: 1.0 },
    al: { key: "al", label: "Kilo almak", factor: 1.15, proteinPerKg: 1.6, fatPct: 0.3, mealTarget: 1.0 },
    kas: { key: "kas", label: "Kas yapmak", factor: 1.1, proteinPerKg: 2.0, fatPct: 0.25, mealTarget: 1.0 },
  };
  const MEAL_SHARE = 0.3; // üç ana öğün + ara öğün payı
  const LIMITS = { yas: [15, 90], boy: [120, 230], kilo: [35, 250] };
  const MACRO_RESULTS = 12;

  function calcMacros(f) {
    const goal = GOALS[f.hedef];
    const bmr = 10 * f.kilo + 6.25 * f.boy - 5 * f.yas + (f.cinsiyet === "erkek" ? 5 : -161);
    const tdee = bmr * Number(f.aktivite);
    const floor = f.cinsiyet === "erkek" ? 1500 : 1200;
    const kcal = Math.round(Math.max(tdee * goal.factor, Math.min(floor, tdee)));
    let protein = f.kilo * goal.proteinPerKg;
    protein = Math.min(protein, (kcal * 0.35) / 4);
    const fat = (kcal * goal.fatPct) / 9;
    const carbs = Math.max(0, (kcal - protein * 4 - fat * 9) / 4);
    const bmi = f.kilo / (f.boy / 100) ** 2;
    return {
      bmr: Math.round(bmr),
      tdee: Math.round(tdee),
      kcal,
      protein: Math.round(protein),
      fat: Math.round(fat),
      carbs: Math.round(carbs),
      bmi: Math.round(bmi * 10) / 10,
      meal: Math.round(kcal * MEAL_SHARE),
      goal,
    };
  }

  // "%79'u", "%87'si", "%100'ü": iyelik eki sayının okunuşundaki son sesli harfe göre seçilir.
  function pctTr(n) {
    const v = Math.abs(Math.round(n));
    const ONES = ["", "i", "si", "ü", "ü", "i", "sı", "si", "i", "u"];
    const TENS = ["", "u", "si", "u", "ı", "si", "ı", "i", "i", "ı"];
    let suffix;
    if (v === 0) suffix = "ı";
    else if (v % 1000 === 0) suffix = "i";
    else if (v % 100 === 0) suffix = "ü";
    else if (v % 10 === 0) suffix = TENS[(v / 10) % 10];
    else suffix = ONES[v % 10];
    return `%${v}'${suffix}`;
  }

  function bmiLabel(bmi) {
    if (bmi < 18.5) return "zayıf";
    if (bmi < 25) return "normal";
    if (bmi < 30) return "fazla kilolu";
    return "obez";
  }

  // Tarifin bu kişiye uygunluğu: önerilen porsiyon ile öğün kalorisine yakınlık,
  // protein oranı ve yağ oranı birlikte puanlanır.
  function scoreRecipe(r, m) {
    const n = r.nutrition;
    if (!n || !n.calories) return null;
    const target = m.meal * m.goal.mealTarget;
    const portion = Math.min(2, Math.max(0.5, Math.round((target / n.calories) * 2) / 2));
    const kcal = n.calories * portion;
    const calFit = 1 - Math.min(1, Math.abs(kcal / target - 1) / 0.5);
    const proteinShare = (n.protein * 4) / n.calories;
    const targetShare = (m.protein * 4) / m.kcal;
    // Hedefin %30 üstüne kadar fazla protein de puan kazandırır (kas/kilo verme için önemli).
    const protScore = Math.min(1.3, proteinShare / targetShare) / 1.3;
    const fatShare = (n.fat * 9) / n.calories;
    const fatScore = 1 - Math.min(1, Math.max(0, fatShare - m.goal.fatPct - 0.1) / 0.3);
    const W = {
      kas: [0.3, 0.5, 0.2],
      ver: [0.35, 0.45, 0.2],
      koru: [0.45, 0.3, 0.25],
      al: [0.5, 0.3, 0.2],
    }[m.goal.key];
    let score = W[0] * calFit + W[1] * protScore + W[2] * fatScore;
    if ((n.confidence ?? 1) < 0.6) score *= 0.9;
    return {
      r,
      score,
      portion,
      kcal: Math.round(kcal),
      protein: Math.round(n.protein * portion),
      carbs: Math.round(n.carbs * portion),
      fat: Math.round(n.fat * portion),
      mealPct: Math.round((kcal / m.meal) * 100),
      highProtein: proteinShare >= targetShare,
    };
  }

  function readMacroForm(form) {
    const fd = new FormData(form);
    const num = (k) => Number(String(fd.get(k) || "").replace(",", "."));
    return {
      cinsiyet: fd.get("cinsiyet") || "",
      aktivite: fd.get("aktivite") || "",
      hedef: fd.get("hedef") || "",
      yas: num("yas"),
      boy: num("boy"),
      kilo: num("kilo"),
    };
  }

  function validateMacro(f) {
    const errors = {};
    if (!f.cinsiyet) errors.cinsiyet = "Lütfen cinsiyet seçiniz.";
    if (!f.aktivite) errors.aktivite = "Lütfen aktivite düzeyi seçiniz.";
    if (!GOALS[f.hedef]) errors.hedef = "Lütfen hedef seçiniz.";
    const range = (k, label, unit) => {
      const [lo, hi] = LIMITS[k];
      if (!f[k]) errors[k] = `Lütfen ${label} giriniz.`;
      else if (f[k] < lo || f[k] > hi) {
        errors[k] = `${label.charAt(0).toLocaleUpperCase("tr")}${label.slice(1)} ${lo}-${hi}${unit} arasında olmalı.`;
      }
    };
    range("yas", "yaş", "");
    range("boy", "boy", " cm");
    range("kilo", "kilo", " kg");
    return errors;
  }

  function macroShareUrl(f) {
    const p = new URLSearchParams({ c: f.cinsiyet, a: f.aktivite, h: f.hedef, y: f.yas, b: f.boy, k: f.kilo });
    return `${location.origin}/makro?${p}`;
  }

  function macroEmbedCode() {
    const src = `${location.origin}/makro?embed=1`;
    return `<iframe src="${src}" title="Günlük makro besin ihtiyacı hesaplama aracı" width="100%" height="1100" style="border:0" loading="lazy"></iframe>`;
  }

  function radio(name, value, label, checked) {
    return `<label class="calc-radio"><input type="radio" name="${name}" value="${value}"${checked ? " checked" : ""}> <span>${esc(label)}</span></label>`;
  }

  function renderMacro(prefill = {}) {
    const p = prefill;
    els.viewMacro.innerHTML = `<div class="container macro">
      <form id="macro-form" class="calc" novalidate>
        <fieldset class="calc-box">
          <legend class="calc-legend">Günlük Makro Besin İhtiyacı Hesaplama Aracı</legend>
          <p class="calc-required"><span class="req" aria-hidden="true">*</span> Doldurulması zorunlu alanlar.</p>

          <div class="calc-row" role="radiogroup" aria-labelledby="lbl-cinsiyet" data-field="cinsiyet">
            <span class="calc-label" id="lbl-cinsiyet"><span class="req" aria-hidden="true">*</span> Cinsiyet:</span>
            <div class="calc-control calc-stack">
              ${radio("cinsiyet", "kadin", "Kadın", p.cinsiyet === "kadin")}
              ${radio("cinsiyet", "erkek", "Erkek", p.cinsiyet === "erkek")}
              <p class="calc-error" id="err-cinsiyet"></p>
            </div>
          </div>

          <div class="calc-row" data-field="aktivite">
            <label class="calc-label" for="aktivite"><span class="req" aria-hidden="true">*</span> Aktivite Düzeyi:</label>
            <div class="calc-control">
              <select id="aktivite" name="aktivite" class="calc-select">
                <option value="">Lütfen seçiniz</option>
                ${ACTIVITY.map((a) => `<option value="${a.value}"${p.aktivite === a.value ? " selected" : ""}>${esc(a.label)}</option>`).join("")}
              </select>
              <p class="calc-error" id="err-aktivite"></p>
            </div>
          </div>

          <div class="calc-row" role="radiogroup" aria-labelledby="lbl-hedef" data-field="hedef">
            <span class="calc-label" id="lbl-hedef"><span class="req" aria-hidden="true">*</span> Hedef:</span>
            <div class="calc-control calc-stack">
              ${Object.entries(GOALS).map(([k, g]) => radio("hedef", k, g.label, p.hedef === k)).join("")}
              <p class="calc-error" id="err-hedef"></p>
            </div>
          </div>

          <div class="calc-row" data-field="yas">
            <label class="calc-label" for="yas"><span class="req" aria-hidden="true">*</span> Yaş:</label>
            <div class="calc-control"><div class="calc-inline">
              <input id="yas" name="yas" class="calc-input" inputmode="numeric" autocomplete="off" value="${esc(p.yas || "")}">
              <span class="calc-hint">Örn. 32</span></div>
              <p class="calc-error" id="err-yas"></p>
            </div>
          </div>

          <div class="calc-row" data-field="boy">
            <label class="calc-label" for="boy"><span class="req" aria-hidden="true">*</span> Boy:</label>
            <div class="calc-control"><div class="calc-inline">
              <input id="boy" name="boy" class="calc-input" inputmode="numeric" autocomplete="off" value="${esc(p.boy || "")}">
              <span class="calc-hint">cm (Örn. 172)</span></div>
              <p class="calc-error" id="err-boy"></p>
            </div>
          </div>

          <div class="calc-row" data-field="kilo">
            <label class="calc-label" for="kilo"><span class="req" aria-hidden="true">*</span> Kilo:</label>
            <div class="calc-control"><div class="calc-inline">
              <input id="kilo" name="kilo" class="calc-input" inputmode="decimal" autocomplete="off" value="${esc(p.kilo || "")}">
              <span class="calc-hint">kg (Örn. 69)</span></div>
              <p class="calc-error" id="err-kilo"></p>
            </div>
          </div>

          <div class="calc-actions">
            <button type="submit" class="calc-btn calc-btn-primary">Hesapla</button>
            <button type="reset" class="calc-btn calc-btn-reset">Sıfırla</button>
          </div>

          <div class="calc-tools">
            <button type="button" class="calc-pill" data-macro="share">
              <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><circle cx="18" cy="5" r="2.6" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="6" cy="12" r="2.6" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="18" cy="19" r="2.6" fill="none" stroke="currentColor" stroke-width="2"/><path d="m8.3 10.8 7.4-4.4M8.3 13.2l7.4 4.4" stroke="currentColor" stroke-width="2"/></svg>
              Paylaş
            </button>
            <button type="button" class="calc-pill" data-macro="embed" aria-expanded="false" aria-controls="embed-box">
              <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path d="m8 6-6 6 6 6M16 6l6 6-6 6" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>
              Sitene Ekle
            </button>
          </div>
          <p class="calc-toast" role="status" aria-live="polite"></p>
          <div id="embed-box" class="embed-box" hidden>
            <label for="embed-code">Aşağıdaki kodu kendi sitenize yapıştırın:</label>
            <textarea id="embed-code" readonly rows="3">${esc(macroEmbedCode())}</textarea>
            <button type="button" class="calc-pill" data-macro="copy-embed">Kodu kopyala</button>
          </div>
        </fieldset>
      </form>
      <div id="macro-result" class="macro-result" aria-live="polite"></div>
    </div>`;
  }

  function showMacroErrors(form, errors) {
    form.querySelectorAll(".calc-row").forEach((row) => {
      const key = row.dataset.field;
      const msg = errors[key] || "";
      row.classList.toggle("has-error", Boolean(msg));
      const out = row.querySelector(".calc-error");
      if (out) out.textContent = msg;
      row.querySelectorAll("input, select").forEach((el) => {
        if (el.type !== "radio") el.setAttribute("aria-invalid", String(Boolean(msg)));
      });
    });
  }

  function macroTile(label, grams, kcalPer, total, cls) {
    const pct = Math.round(((grams * kcalPer) / total) * 100);
    return `<div class="macro-tile ${cls}">
      <span class="macro-tile-label">${label}</span>
      <span class="macro-tile-value">${grams} g</span>
      <div class="macro-bar"><span style="width:${pct}%"></span></div>
      <span class="macro-tile-pct">günlük kalorinin ${pctTr(pct)}</span>
    </div>`;
  }

  function macroCardHtml(s) {
    const r = s.r;
    const embed = document.documentElement.classList.contains("is-embed");
    const href = embed
      ? `${location.origin}/tarif/${encodeURIComponent(r.slug)}`
      : `/tarif/${encodeURIComponent(r.slug)}`;
    const portion = s.portion === 1 ? "1 porsiyon" : `${String(s.portion).replace(".", ",")} porsiyon`;
    return `<li><a class="recipe-card" href="${esc(href)}"${embed ? ' target="_blank" rel="noopener"' : ""}>
      <div class="card-media">${imageHtml(r)}<span class="card-badge">${s.kcal} kcal</span>
        ${s.highProtein ? '<span class="card-flag">yüksek protein</span>' : ""}</div>
      <h3 class="card-title">${esc(r.title)}</h3>
      <div class="card-nutri">
        <p class="nutri-portion">önerilen: <strong>${portion}</strong> · öğün hedefinin ${pctTr(s.mealPct)}</p>
        <p class="nutri-macros"><span>P ${s.protein} g</span><span>K ${s.carbs} g</span><span>Y ${s.fat} g</span></p>
      </div>
    </a></li>`;
  }

  function renderMacroResult(f, m) {
    const box = $("#macro-result");
    const scored = state.recipes.map((r) => scoreRecipe(r, m)).filter(Boolean).sort((a, b) => b.score - a.score);
    if (!scored.length) {
      box.innerHTML = `<div class="empty-state"><strong>tariflerde besin bilgisi bulunamadı</strong>
        backend klasöründe <code>python main.py --retag</code> komutunu çalıştırın.</div>`;
      return;
    }
    const cats = [...new Set(scored.map((s) => s.r.category).filter(has))];
    const catOrder = (c) => (CATEGORY_ORDER.includes(c) ? CATEGORY_ORDER.indexOf(c) : 99);
    cats.sort((a, b) => catOrder(a) - catOrder(b));
    const deficit = m.kcal - m.tdee;
    const youngNote = f.yas < 18 ? "<li>18 yaş altı için bu formüller büyüme ihtiyacını hesaba katmaz; bir uzmana danışın.</li>" : "";

    box.innerHTML = `<section class="macro-summary" aria-labelledby="macro-sum-title">
        <h2 id="macro-sum-title" class="macro-heading">günlük ihtiyacın</h2>
        <div class="macro-grid">
          <div class="macro-kcal">
            <span class="macro-kcal-value">${m.kcal.toLocaleString("tr-TR")}</span>
            <span class="macro-kcal-unit">kcal / gün</span>
            <span class="macro-kcal-goal">${esc(m.goal.label.toLocaleLowerCase("tr"))}${deficit ? ` (${deficit > 0 ? "+" : ""}${deficit.toLocaleString("tr-TR")} kcal)` : ""}</span>
          </div>
          ${macroTile("protein", m.protein, 4, m.kcal, "is-protein")}
          ${macroTile("karbonhidrat", m.carbs, 4, m.kcal, "is-carbs")}
          ${macroTile("yağ", m.fat, 9, m.kcal, "is-fat")}
        </div>
        <dl class="macro-facts">
          <div><dt>bazal metabolizma</dt><dd>${m.bmr.toLocaleString("tr-TR")} kcal</dd></div>
          <div><dt>günlük harcama</dt><dd>${m.tdee.toLocaleString("tr-TR")} kcal</dd></div>
          <div><dt>öğün başına</dt><dd>≈ ${m.meal.toLocaleString("tr-TR")} kcal</dd></div>
          <div><dt>beden kitle indeksi</dt><dd>${String(m.bmi).replace(".", ",")} (${bmiLabel(m.bmi)})</dd></div>
        </dl>
        <ul class="macro-notes">
          <li>Hesaplama Mifflin-St Jeor formülüne dayanır; tarif besin değerleri malzeme listesinden <strong>tahmin</strong> edilmiştir ve ±%20-30 sapabilir.</li>
          <li>Bu araç tıbbi tavsiye değildir. Sağlık durumunuz, hamilelik ya da özel bir diyet için diyetisyene danışın.</li>
          ${youngNote}
        </ul>
      </section>

      <section class="macro-recipes" aria-labelledby="macro-rec-title">
        <div class="macro-recipes-head">
          <h2 id="macro-rec-title" class="macro-heading">sana uygun tarifler</h2>
          <label class="macro-filter">kategori:
            <select id="macro-cat">
              <option value="">tümü</option>
              ${cats.map((c) => `<option value="${esc(c)}">${esc(categoryLabel(c))}</option>`).join("")}
            </select>
          </label>
        </div>
        <p class="macro-recipes-lead">öğün başına ≈ ${m.meal} kcal hedefine, protein ve yağ oranına göre sıralandı. önerilen porsiyon bu hedefe göre hesaplandı.</p>
        <ul id="macro-grid" class="recipe-grid macro-grid-cards" role="list"></ul>
      </section>`;

    const draw = () => {
      const cat = $("#macro-cat").value;
      const list = scored.filter((s) => !cat || s.r.category === cat).slice(0, MACRO_RESULTS);
      $("#macro-grid").innerHTML = list.map(macroCardHtml).join("");
    };
    $("#macro-cat").addEventListener("change", draw);
    draw();
  }

  function submitMacro(form, { scroll = true } = {}) {
    const f = readMacroForm(form);
    const errors = validateMacro(f);
    showMacroErrors(form, errors);
    if (Object.keys(errors).length) {
      $("#macro-result").innerHTML = "";
      const first = form.querySelector(".has-error input, .has-error select");
      if (first && scroll) first.focus();
      return;
    }
    state.macroForm = f;
    renderMacroResult(f, calcMacros(f));
    const params = new URLSearchParams({ c: f.cinsiyet, a: f.aktivite, h: f.hedef, y: f.yas, b: f.boy, k: f.kilo });
    if (document.documentElement.classList.contains("is-embed")) params.set("embed", "1");
    history.replaceState(null, "", `/makro?${params}`);
    if (scroll) $("#macro-result").scrollIntoView({ block: "start" });
  }

  function macroToast(text) {
    const t = $(".calc-toast");
    if (!t) return;
    t.textContent = text;
    clearTimeout(macroToast.timer);
    macroToast.timer = setTimeout(() => (t.textContent = ""), 3500);
  }

  async function copyText(text) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (_) {
      return false;
    }
  }

  function bindMacroEvents() {
    els.viewMacro.addEventListener("submit", (e) => {
      if (e.target.id !== "macro-form") return;
      e.preventDefault();
      submitMacro(e.target);
    });
    els.viewMacro.addEventListener("reset", (e) => {
      if (e.target.id !== "macro-form") return;
      showMacroErrors(e.target, {});
      $("#macro-result").innerHTML = "";
      state.macroForm = null;
      history.replaceState(null, "", document.documentElement.classList.contains("is-embed") ? "/makro?embed=1" : "/makro");
    });
    els.viewMacro.addEventListener("click", async (e) => {
      const btn = e.target.closest("[data-macro]");
      if (!btn) return;
      const action = btn.dataset.macro;
      if (action === "share") {
        const form = $("#macro-form");
        const f = readMacroForm(form);
        const filled = !Object.keys(validateMacro(f)).length;
        const url = filled ? macroShareUrl(f) : `${location.origin}/makro`;
        if (navigator.share) {
          try {
            await navigator.share({ title: "Günlük makro besin ihtiyacı", url });
            return;
          } catch (_) {
            /* kullanıcı paylaşımı iptal ettiyse panoya kopyalamaya düş */
          }
        }
        macroToast((await copyText(url))
          ? (filled ? "Sonuç bağlantısı panoya kopyalandı." : "Araç bağlantısı panoya kopyalandı.")
          : url);
      } else if (action === "embed") {
        const box = $("#embed-box");
        box.hidden = !box.hidden;
        btn.setAttribute("aria-expanded", String(!box.hidden));
        if (!box.hidden) $("#embed-code").select();
      } else if (action === "copy-embed") {
        macroToast((await copyText($("#embed-code").value)) ? "Kod panoya kopyalandı." : "Kodu seçip kopyalayın.");
      }
    });
  }

  function routeMacro(query) {
    const q = new URLSearchParams(query || "");
    const prefill = q.has("c")
      ? { cinsiyet: q.get("c"), aktivite: q.get("a"), hedef: q.get("h"), yas: q.get("y"), boy: q.get("b"), kilo: q.get("k") }
      : state.macroForm
        ? { ...state.macroForm }
        : {};
    renderMacro(prefill);
    if (prefill.cinsiyet) submitMacro($("#macro-form"), { scroll: false });
  }

  function nutritionHtml(r) {
    const n = r.nutrition;
    if (!n || !n.calories) return "";
    return `<div class="detail-nutri" aria-label="tahmini besin değerleri">
      <div class="detail-nutri-head"><h2>besin değerleri</h2><span>1 porsiyon · tahmini</span></div>
      <div class="detail-nutri-grid">
        <div><strong>${n.calories}</strong><span>kcal</span></div>
        <div><strong>${n.protein} g</strong><span>protein</span></div>
        <div><strong>${n.carbs} g</strong><span>karbonhidrat</span></div>
        <div><strong>${n.fat} g</strong><span>yağ</span></div>
      </div>
    </div>`;
  }

  // ------------------------------------------------------------------ //
  // Başlangıç
  // ------------------------------------------------------------------ //
  function renderSkeleton() {
    els.grid.innerHTML = Array.from({ length: 8 }, () =>
      `<li class="recipe-card skeleton" aria-hidden="true"><div class="card-media"></div><div class="card-title"><span></span></div></li>`
    ).join("");
  }

  function renderLoadError(err) {
    console.error("recipes.json yüklenemedi:", err);
    els.grid.innerHTML = `<li class="empty-state"><strong>tarifler yüklenemedi</strong>
      siteyi proje kökünden bir yerel sunucuyla açtığınızdan ve <code>backend/output/recipes.json</code>
      dosyasının var olduğundan emin olun (bkz. README).</li>`;
    els.filters.innerHTML = "";
    els.catTrack.innerHTML = "";
    els.resultInfo.textContent = "";
  }

  async function init() {
    upgradeHashUrl();
    // ?embed=1 ile açılırsa (Sitene Ekle) yalnızca araç gösterilir.
    if (new URLSearchParams(location.search).get("embed") === "1") {
      document.documentElement.classList.add("is-embed");
    }
    bindEvents();
    renderSkeleton();
    try {
      const res = await fetch(DATA_URL, { cache: "no-cache" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (!data || !Array.isArray(data.recipes)) throw new Error("Beklenmeyen JSON yapısı");

      state.meta = data.meta || null;
      state.recipes = data.recipes
        .filter((r) => r && r.slug && r.title)
        .map((r) => ({
          ...r,
          ingredients: Array.isArray(r.ingredients) ? r.ingredients : [],
          ingredient_count: Number(r.ingredient_count) || (Array.isArray(r.ingredients) ? r.ingredients.length : 0),
          duration_minutes: Number(r.duration_minutes) || 0,
          ingredient_tags: Array.isArray(r.ingredient_tags) ? r.ingredient_tags : [],
        }));
      state.catalog = Array.isArray(state.meta?.ingredients) ? state.meta.ingredients : [];
      state.catalogByName = new Map(state.catalog.map((i) => [i.name, i]));
      state.ingredientGroups = Array.isArray(state.meta?.ingredient_groups)
        ? state.meta.ingredient_groups
        : [...new Set(state.catalog.map((i) => i.group))];
      loadPantry();
      state.bySlug = new Map(state.recipes.map((r) => [r.slug, r]));
      state.groups = buildGroups();

      renderFooter();
      route();
    } catch (err) {
      renderLoadError(err);
    }
  }

  init();
})();
