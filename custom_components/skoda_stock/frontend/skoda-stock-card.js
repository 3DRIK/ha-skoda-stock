/* Škoda Stock card – served by the skoda_stock integration (no manual resource needed). */
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fold = (s) => String(s || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
const eur = (n) => (n == null ? "–" : new Intl.NumberFormat("sk-SK", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(n));
const day = (s) => (s ? new Date(s).toLocaleDateString("sk-SK", { day: "numeric", month: "numeric", year: "numeric" }) : "");
const DAY = 864e5;
const LS = "skoda-stock-card-filters";
const DEFAULTS = { q: "", model: "all", fav: false, fresh: false, drop: false, hideRes: false, demo: "all", maxPrice: "", sort: "offer", pk: [], ft: [], eqMode: "all" };
const SORTS = { offer: "Najnovšie ponuky", price_asc: "Cena od najnižšej", price_desc: "Cena od najvyššej", discount: "Najväčšia zľava", km: "Najmenej km", range: "Najväčší dojazd" };
const TECH = { ElectricCarBatteryCapacity: "Čistá kapacita batérie", MaximumDcChargingPower: "Max. DC nabíjanie", BatteryChargingTime80_SOC_Max_DC: "Nabíjanie na 80 % (DC)",
  BatteryChargingTimeAC11_100_SOC: "Nabíjanie AC 11 kW na 100 %", Acceleration: "Zrýchlenie 0–100 km/h", MaxSpeed: "Max. rýchlosť", LuggageCapacity: "Batožinový priestor",
  TowingWeightBraked12: "Ťažné zariadenie (brzdené)", "Payload.WithDriver": "Užitočná hmotnosť" };
const DEMO_STEPS = ["all", "only", "none"];
const DEMO_LABEL = { all: "Nové aj predvádzacie", only: "Iba predvádzacie", none: "Bez predvádzacích" };

const CSS = `
:host { display:block }
ha-card { background:linear-gradient(135deg,#1a1f2e,#1e2438); color:#e5e9f2; border-radius:16px; padding:16px; overflow:hidden }
.head { display:flex; align-items:center; justify-content:space-between; gap:12px }
.title { font-size:1.25rem; font-weight:600 }
.sub { color:#8b93a7; font-size:.85rem; margin-top:2px }
button { font:inherit; color:inherit; cursor:pointer }
button:focus-visible, a:focus-visible, input:focus-visible, select:focus-visible { outline:2px solid #60a5fa; outline-offset:2px }
.icon { background:rgba(96,165,250,.12); border:0; border-radius:12px; width:40px; height:40px; font-size:1.2rem }
.icon.spin { animation:spin 1s linear infinite }
@keyframes spin { to { transform:rotate(360deg) } }
.filters { display:grid; gap:10px; margin:14px 0 }
input[type=search], input[type=number], select { background:rgba(255,255,255,.06); color:#e5e9f2; border:1px solid rgba(255,255,255,.1); border-radius:12px; padding:10px 12px; font:inherit; min-width:0 }
select option { color:#111 }
.chips { display:flex; flex-wrap:wrap; gap:8px }
.chip { background:rgba(255,255,255,.06); border:1px solid rgba(255,255,255,.1); border-radius:999px; padding:6px 12px; font-size:.85rem }
.chip.on { background:#60a5fa; border-color:#60a5fa; color:#0f172a; font-weight:600 }
.row { display:flex; gap:10px; flex-wrap:wrap; align-items:center }
.row select { flex:1 1 180px }
.row label { display:flex; align-items:center; gap:8px; color:#8b93a7; font-size:.9rem }
.row input[type=number] { width:110px }
.car { position:relative; background:rgba(255,255,255,.04); border:1px solid rgba(255,255,255,.07); border-radius:16px; padding:12px; margin-bottom:10px }
.car.gone { opacity:.55 }
.top { display:flex; gap:12px; align-items:flex-start }
.top img { width:104px; height:62px; object-fit:contain; flex:none }
.main { flex:1; min-width:0 }
.t { font-weight:600; padding-right:34px }
.s { color:#8b93a7; font-size:.85rem; margin-top:2px }
.price { text-align:right; flex:none }
.p { font-size:1.15rem; font-weight:700; white-space:nowrap }
.lp { color:#8b93a7; font-size:.8rem; text-decoration:line-through }
.chg { font-size:.8rem; font-weight:600 }
.chg.down { color:#34d399 } .chg.up { color:#f87171 }
.tags { display:flex; flex-wrap:wrap; gap:6px; margin-top:6px }
.tag { font-size:.75rem; padding:2px 8px; border-radius:999px; background:rgba(255,255,255,.08) }
.tag.new { background:rgba(96,165,250,.2); color:#93c5fd } .tag.res { background:rgba(251,191,36,.18); color:#fcd34d }
.tag.demo { background:rgba(167,139,250,.2); color:#c4b5fd } .tag.drop { background:rgba(52,211,153,.18); color:#6ee7b7 }
.star { position:absolute; top:8px; right:8px; background:none; border:0; font-size:1.4rem; color:#8b93a7; line-height:1 }
.star.on { color:#fbbf24 }
.links { display:flex; gap:14px; flex-wrap:wrap; margin-top:10px; font-size:.9rem; align-items:center }
.links a, .links button { color:#60a5fa; text-decoration:none; background:none; border:0; padding:0 }
.det { margin-top:10px; display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:6px 16px; font-size:.85rem }
.det span { color:#8b93a7 } .det a { color:#60a5fa }
.spark { grid-column:1/-1 }
.more, .empty { width:100%; padding:12px; border-radius:12px; border:1px dashed rgba(255,255,255,.2); background:none; text-align:center; color:#8b93a7 }
details.eq { background:rgba(255,255,255,.04); border:1px solid rgba(255,255,255,.08); border-radius:12px; padding:8px 12px }
details.eq summary { cursor:pointer; font-weight:600 }
.eqbox { display:grid; gap:10px; margin-top:10px }
#eqopts { max-height:260px; overflow:auto; display:grid; gap:2px }
.opt { display:flex; align-items:center; gap:8px; padding:4px 2px; font-size:.9rem }
.opt span { flex:1; min-width:0 } .opt em { color:#8b93a7; font-style:normal; font-size:.8rem }
.grp { color:#8b93a7; font-size:.8rem; margin-top:6px }
.tag.pk { background:rgba(96,165,250,.12); color:#bfdbfe }
@media (max-width:480px) { .top { flex-wrap:wrap } .price { text-align:left; width:100% } }
`;

class SkodaStockCard extends HTMLElement {
  setConfig(config) {
    this._config = { title: "Škoda sklad", page_size: 25, ...config };
    let saved = {};
    try { saved = JSON.parse(localStorage.getItem(LS) || "{}"); } catch (e) { /* ignore */ }
    this._f = { ...DEFAULTS, ...saved };
    this._open = new Set();
    this._shown = this._config.page_size;
    if (this._root) this._renderAll();
  }
  getCardSize() { return 10; }
  static getStubConfig() { return {}; }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) { this._build(); this._load(); this._subscribe(); }
  }
  connectedCallback() { if (this._hass && !this._unsub) { this._subscribe(); this._load(); } }
  disconnectedCallback() { if (this._unsub) { this._unsub.then((u) => u()).catch(() => {}); this._unsub = null; } }

  _subscribe() {
    this._unsub = this._hass.connection.subscribeEvents(() => this._load(), "skoda_stock_updated");
    this._unsub.catch(() => { this._unsub = null; });
  }
  async _load() {
    try {
      this._data = await this._hass.callWS({ type: "skoda_stock/list" });

      for (const c of this._data.cars) {
        c._s = fold([
          c.model,
          c.title,
          c.dealer_name,
          c.dealer_city,
          c.color,
          c.interior,
          c.vin,
          c.commission
        ].join(" "));

        c._has = Array.isArray(c.ft);
        c._ft = new Set(c.ft || []);
        c._pk = new Set((c.packages || []).map((p) => p.t));
      }

      this._err = null;
    } catch (e) {
      this._err = "Integrácia Škoda Stock nie je načítaná. Pridaj ju v Nastavenia → Zariadenia a služby.";
    }
    this._renderAll();
  }
  _save() { try { localStorage.setItem(LS, JSON.stringify(this._f)); } catch (e) { /* ignore */ } }

  _build() {
    this._root = this.attachShadow({ mode: "open" });
    this._root.innerHTML = `<style>${CSS}</style><ha-card>
      <div class="head"><div><div class="title">${esc(this._config.title)}</div><div class="sub" id="sub"></div></div>
        <button class="icon" id="refresh" title="Obnoviť" aria-label="Obnoviť">↻</button></div>
      <div class="filters">
        <input id="q" type="search" placeholder="Hľadať verziu, predajcu, mesto, farbu alebo VIN" aria-label="Hľadať">
        <div class="chips" id="chips"></div>
        <details class="eq" id="eq"><summary>Výbava a balíky <span id="eqn"></span></summary>
          <div class="eqbox"><input id="eqq" type="search" placeholder="Hľadať výbavu, napr. tepelné čerpadlo" aria-label="Hľadať výbavu">
            <div id="eqopts"></div></div></details>
        <div class="chips" id="eqsel"></div>
        <div class="row"><select id="sort" aria-label="Zoradenie"></select>
          <label>Cena do <input id="maxp" type="number" step="500" min="0" inputmode="numeric"></label></div>
      </div><div id="list"></div></ha-card>`;
    const $ = (id) => this._root.getElementById(id);
    $("sort").innerHTML = Object.entries(SORTS).map(([k, v]) => `<option value="${k}">${v}</option>`).join("");
    $("q").value = this._f.q; $("sort").value = this._f.sort; $("maxp").value = this._f.maxPrice;
    $("q").addEventListener("input", (e) => { this._f.q = e.target.value; this._changed(); });
    $("sort").addEventListener("change", (e) => { this._f.sort = e.target.value; this._changed(); });
    $("maxp").addEventListener("input", (e) => { this._f.maxPrice = e.target.value; this._changed(); });
    $("refresh").addEventListener("click", async (e) => {
      e.currentTarget.classList.add("spin");
      try { await this._hass.callWS({ type: "skoda_stock/refresh" }); } catch (err) { /* ignore */ }
      e.currentTarget.classList.remove("spin");
    });
    $("chips").addEventListener("click", (e) => {
      const b = e.target.closest("[data-chip]"); if (!b) return;
      const k = b.dataset.chip, v = b.dataset.val;
      if (k === "model") this._f.model = v;
      else if (k === "demo") this._f.demo = DEMO_STEPS[(DEMO_STEPS.indexOf(this._f.demo) + 1) % 3];
      else this._f[k] = !this._f[k];
      this._changed();
    });
    $("list").addEventListener("click", (e) => this._onList(e));
    $("eqq").addEventListener("input", () => this._renderEq());
    $("eqopts").addEventListener("change", (e) => {
      const i = e.target.closest("[data-eq]"); if (!i) return;
      const arr = this._f[i.dataset.eq], k = arr.indexOf(i.dataset.id);
      if (i.checked && k < 0) arr.push(i.dataset.id);
      if (!i.checked && k >= 0) arr.splice(k, 1);
      this._changed();
    });
    $("eqsel").addEventListener("click", (e) => {
      const b = e.target.closest("[data-eqx]"), m = e.target.closest("[data-eqmode]");
      if (m) { this._f.eqMode = this._f.eqMode === "all" ? "any" : "all"; this._changed(); return; }
      if (!b) return;
      const arr = this._f[b.dataset.eqx], k = arr.indexOf(b.dataset.id);
      if (k >= 0) arr.splice(k, 1);
      this._changed(); this._renderEq();
    });
  }
  _changed() { this._shown = this._config.page_size; this._save(); this._renderChips(); this._renderEqSel(); this._renderList(); }
  _renderAll() { if (!this._root) return; this._buildEq(); this._renderChips(); this._renderEq(); this._renderEqSel(); this._renderList(); this._renderSub(); }

  async _onList(e) {
    const more = e.target.closest("[data-more]");
    if (more) { this._shown += this._config.page_size; this._renderList(); return; }
    const el = e.target.closest("[data-vin]"); if (!el) return;
    const vin = el.dataset.vin, act = e.target.closest("[data-act]")?.dataset.act;
    const car = this._data.cars.find((c) => c.vin === vin);
    if (act === "fav" && car) {
      car.favorite = !car.favorite; this._renderChips(); this._renderList();
      try { await this._hass.callWS({ type: "skoda_stock/favorite", vin, favorite: car.favorite }); } catch (err) { car.favorite = !car.favorite; this._renderList(); }
    } else if (act === "open") {
      this._open.has(vin) ? this._open.delete(vin) : this._open.add(vin); this._renderList();
    }
  }

  _buildEq() {
    if (!this._data) return;
    const act = this._data.cars.filter((c) => !c.removed_at), pk = new Map(), ft = new Map();
    for (const c of act) {
      for (const t of c._pk) pk.set(t, (pk.get(t) || 0) + 1);
      for (const id of c._ft) ft.set(id, (ft.get(id) || 0) + 1);
    }
    this._eq = { pk, ft, total: act.length, missing: act.filter((c) => !c._has).length };
  }
  _label(type, id) { return type === "pk" ? id : (this._data?.catalog?.[id]?.t || id); }
  _renderEq() {
    const box = this._root.getElementById("eqopts"); if (!box || !this._eq) return;
    const q = fold(this._root.getElementById("eqq").value.trim()), { pk, ft, total } = this._eq, f = this._f;
    const opt = (type, id, n) => `<label class="opt"><input type="checkbox" data-eq="${type}" data-id="${esc(id)}" ${f[type].includes(id) ? "checked" : ""}>
      <span>${esc(this._label(type, id))}</span><em>${n}</em></label>`;
    const pks = [...pk].filter(([t]) => !q || fold(t).includes(q)).sort((a, b) => b[1] - a[1]).map(([t, n]) => opt("pk", t, n));
    const all = [...ft].filter(([id, n]) => (q || n < total) && (!q || fold(this._label("ft", id)).includes(q))).sort((a, b) => b[1] - a[1]);
    const fts = all.slice(0, 60).map(([id, n]) => opt("ft", id, n));
    box.innerHTML = (pks.length ? `<div class="grp">Balíky</div>${pks.join("")}` : "") +
      (fts.length ? `<div class="grp">Výbava${all.length > 60 ? ` (prvých 60 z ${all.length}, zúž hľadanie)` : ""}</div>${fts.join("")}` : "") ||
      `<div class="empty">${this._eq.missing === total ? "Výbava sa ešte načítava." : "Nič sa nenašlo."}</div>`;
  }
  _renderEqSel() {
    const el = this._root.getElementById("eqsel"), n = this._f.pk.length + this._f.ft.length;
    this._root.getElementById("eqn").textContent = n ? `(vybrané: ${n})` : "";
    if (!el) return;
    const chip = (type, id) => `<button class="chip on" data-eqx="${type}" data-id="${esc(id)}" aria-label="Zrušiť filter">${esc(this._label(type, id))} ×</button>`;
    el.innerHTML = [...this._f.pk.map((x) => chip("pk", x)), ...this._f.ft.map((x) => chip("ft", x))].join("") +
      (n > 1 ? `<button class="chip" data-eqmode>${this._f.eqMode === "all" ? "Musí mať všetko" : "Stačí aspoň jedno"}</button>` : "");
  }

  _isFresh(c) { return !c.baseline && Date.now() - Date.parse(c.first_seen) < 2 * DAY; }
  _isDrop(c) { return c.price_prev != null && c.price != null && c.price < c.price_prev && Date.now() - Date.parse(c.price_changed_at) < 7 * DAY; }

  _filtered() {
    if (!this._data) return [];
    const f = this._f, q = fold(f.q.trim()), maxp = Number(f.maxPrice) || 0;
    let L = this._data.cars.filter((c) => !c.removed_at || c.favorite);
    if (q) L = L.filter((c) => q.split(/\s+/).every((w) => c._s.includes(w)));
    if (f.model !== "all") L = L.filter((c) => c.model === f.model);
    if (f.fav) L = L.filter((c) => c.favorite);
    if (f.fresh) L = L.filter((c) => this._isFresh(c));
    if (f.drop) L = L.filter((c) => this._isDrop(c));
    if (f.hideRes) L = L.filter((c) => !c.is_reserved);
    if (f.demo === "only") L = L.filter((c) => c.is_demo);
    if (f.demo === "none") L = L.filter((c) => !c.is_demo);
    const sel = [...f.pk.map((t) => (c) => c._pk.has(t)), ...f.ft.map((id) => (c) => c._ft.has(id))];
    if (sel.length) L = L.filter((c) => c._has && (f.eqMode === "any" ? sel.some((fn) => fn(c)) : sel.every((fn) => fn(c))));
    if (maxp) L = L.filter((c) => c.price != null && c.price <= maxp);
    const by = {
      offer: (a, b) => a.order - b.order,
      price_asc: (a, b) => (a.price ?? 1e9) - (b.price ?? 1e9),
      price_desc: (a, b) => (b.price ?? 0) - (a.price ?? 0),
      discount: (a, b) => (b.discount ?? 0) - (a.discount ?? 0),
      km: (a, b) => (a.mileage_km ?? 0) - (b.mileage_km ?? 0),
      range: (a, b) => (b.range_km ?? 0) - (a.range_km ?? 0),
    }[f.sort];
    return L.sort(by);
  }

  _renderSub() {
    const sub = this._root.getElementById("sub"); if (!sub) return;
    if (this._err || !this._data) { sub.textContent = ""; return; }
    const act = this._data.cars.filter((c) => !c.removed_at).length;
    const upd = this._data.updated_at ? new Date(this._data.updated_at).toLocaleString("sk-SK", { dateStyle: "short", timeStyle: "short" }) : "–";
    const miss = this._eq ? this._eq.missing : 0;
    sub.textContent = `${act} áut v ponuke, aktualizované ${upd}` + (miss ? `, výbava sa načítava pre ${miss} áut` : "");
  }

  _renderChips() {
    const el = this._root.getElementById("chips"); if (!el || !this._data) return;
    const f = this._f, models = [...new Set(this._data.cars.map((c) => c.model).filter(Boolean))].sort();
    const favN = this._data.cars.filter((c) => c.favorite).length;
    const chip = (k, label, on, val = "") => `<button class="chip ${on ? "on" : ""}" data-chip="${k}" data-val="${esc(val)}" aria-pressed="${on}">${esc(label)}</button>`;
    el.innerHTML = [chip("model", "Všetky modely", f.model === "all", "all"), ...models.map((m) => chip("model", m, f.model === m, m)),
      chip("fav", `Obľúbené (${favN})`, f.fav), chip("fresh", "Nové (48 h)", f.fresh), chip("drop", "Zlacnené (7 dní)", f.drop),
      chip("hideRes", "Bez rezervovaných", f.hideRes), chip("demo", DEMO_LABEL[f.demo], f.demo !== "all")].join("");
  }

  _spark(h) {
    if (!h || h.length < 2) return h?.length ? `Cena sa nemenila od ${day(h[0][0])}.` : "";
    const W = 260, H = 44, ps = h.map((x) => x[1]), lo = Math.min(...ps), hi = Math.max(...ps), span = hi - lo || 1;
    const pts = h.map((x, i) => `${(i / (h.length - 1)) * W},${H - 4 - ((x[1] - lo) / span) * (H - 8)}`).join(" ");
    return `<svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" role="img" aria-label="Vývoj ceny"><polyline points="${pts}" fill="none" stroke="#60a5fa" stroke-width="2" stroke-linejoin="round"/></svg>
      <div>${eur(ps[0])} (${day(h[0][0])}) → ${eur(ps[ps.length - 1])} (${day(h[h.length - 1][0])})</div>`;
  }

  _item(c) {
    const open = this._open.has(c.vin);
    const drop = c.price_prev != null && c.price < c.price_prev, rise = c.price_prev != null && c.price > c.price_prev;
    const specs = [c.battery_kwh && `${c.battery_kwh} kWh`, c.power_kw && `${c.power_kw} kW`, c.drive, c.range_km && `${c.range_km} km WLTP`].filter(Boolean).join(", ");
    const tags = [
      c.removed_at && `<span class="tag">Preč z ponuky</span>`,
      this._isFresh(c) && `<span class="tag new">Nové</span>`,
      this._isDrop(c) && `<span class="tag drop">Zlacnené</span>`,
      c.is_reserved && `<span class="tag res">Rezervované</span>`,
      ...(c.packages || []).map((p) => `<span class="tag pk">${esc(p.t)}</span>`),
      c.is_demo && `<span class="tag demo">Predvádzacie${c.mileage_km != null ? `, ${c.mileage_km.toLocaleString("sk-SK")} km` : ""}</span>`,
    ].filter(Boolean).join("");
    const det = open ? `<div class="det">
      <div><span>Predajca</span><br>${esc(c.dealer_name)}</div>
      <div><span>Kontakt</span><br>${c.dealer_phone ? `<a href="tel:${esc(c.dealer_phone.split(",")[0].replace(/\s/g, ""))}">${esc(c.dealer_phone)}</a><br>` : ""}${c.dealer_email ? `<a href="mailto:${esc(c.dealer_email)}">${esc(c.dealer_email)}</a>` : ""}</div>
      <div><span>Farba / interiér</span><br>${esc(c.color || "–")}${c.interior ? ` / ${esc(c.interior)}` : ""}</div>
      <div><span>Spotreba</span><br>${c.consumption ? `${c.consumption} kWh/100 km` : "–"}</div>
      <div><span>Výroba</span><br>${esc(c.production_date || "–")}${c.initial_reg ? `, 1. reg. ${day(c.initial_reg)}` : ""}</div>
      <div><span>Dostupnosť</span><br>${esc(c.available_from === "Immediately" ? "Ihneď" : c.available_from || "–")}</div>
      <div><span>VIN</span><br>${esc(c.vin)}</div>
      <div><span>V ponuke od</span><br>${c.baseline ? "pred sledovaním" : day(c.first_seen)}</div>
      ${Object.entries(c.tech || {}).map(([k, v]) => `<div><span>${esc(TECH[k] || k)}</span><br>${esc(v)}</div>`).join("")}
      ${(c.packages || []).map((p) => `<div class="spark"><span>Balík ${esc(p.t)}</span><br>${esc(p.f.map((id) => this._label("ft", id)).join(", "))}</div>`).join("")}
      ${c.ft ? `<div class="spark"><details><summary><span>Všetka výbava (${c.ft.length})</span></summary>${esc(c.ft.map((id) => this._label("ft", id)).join("; "))}</details></div>` : `<div class="spark"><span>Výbava sa ešte načítava.</span></div>`}
      <div class="spark">${this._spark(c.price_history)}</div></div>` : "";
    return `<div class="car ${c.removed_at ? "gone" : ""}" data-vin="${esc(c.vin)}">
      <button class="star ${c.favorite ? "on" : ""}" data-act="fav" aria-pressed="${!!c.favorite}" aria-label="Obľúbené">${c.favorite ? "★" : "☆"}</button>
      <div class="top"><img loading="lazy" alt="" src="${esc(c.image)}">
        <div class="main"><div class="t">${esc(c.model)} ${esc(c.title)}</div>
          <div class="s">${esc(specs)}</div><div class="s">${esc(c.dealer_city || "")}${c.model_year ? `, MY ${c.model_year}` : ""}</div></div>
        <div class="price"><div class="p">${eur(c.price)}</div>
          ${c.list_price && c.list_price > c.price ? `<div class="lp">${eur(c.list_price)}</div>` : ""}
          ${drop || rise ? `<div class="chg ${drop ? "down" : "up"}">${drop ? "−" : "+"}${eur(Math.abs(c.price - c.price_prev))} (${day(c.price_changed_at)})</div>` : ""}</div></div>
      <div class="tags">${tags}</div>
      <div class="links"><a href="${esc(c.url)}" target="_blank" rel="noopener">Na stránke Škoda</a>
        ${c.dealer_website ? `<a href="${esc(c.dealer_website)}" target="_blank" rel="noopener">Predajca</a>` : ""}
        <button data-act="open">${open ? "Skryť detaily" : "Detaily a vývoj ceny"}</button></div>${det}</div>`;
  }

  _renderList() {
    const el = this._root.getElementById("list"); if (!el) return;
    if (this._err) { el.innerHTML = `<div class="empty">${esc(this._err)}</div>`; return; }
    if (!this._data) { el.innerHTML = `<div class="empty">Načítavam…</div>`; return; }
    const L = this._filtered();
    if (!L.length) { el.innerHTML = `<div class="empty">Žiadne auto nevyhovuje filtrom. Skús ich uvoľniť.</div>`; return; }
    const shown = L.slice(0, this._shown);
    el.innerHTML = shown.map((c) => this._item(c)).join("") +
      (L.length > shown.length ? `<button class="more" data-more>Zobraziť ďalších ${Math.min(this._config.page_size, L.length - shown.length)} z ${L.length - shown.length}</button>` : "");
    this._renderSub();
  }
}
customElements.define("skoda-stock-card", SkodaStockCard);
window.customCards = window.customCards || [];
window.customCards.push({ type: "skoda-stock-card", name: "Škoda Stock", description: "Zoznam skladových áut Škoda so sledovaním cien a obľúbenými." });
