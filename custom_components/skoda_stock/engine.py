"""Pure diff/statistics logic (no Home Assistant imports, unit-testable)."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Callable

from .const import (EVT_DROP, EVT_NEW, EVT_REMOVED, EVT_RESERVED, EVT_RISE,
                    EVT_UNRESERVED)

MISSING_THRESHOLD = 2   # consecutive complete fetches before a car counts as removed
PURGE_DAYS = 90
HISTORY_MAX = 60


def new_db() -> dict:
    return {"initialized": False, "cars": {}, "favorites": [], "catalog": {}}


def fmt_eur(v: float | None) -> str:
    if v is None:
        return "–"
    return f"{int(round(v)):,}".replace(",", "\u00a0") + "\u00a0€"


def label(car: dict) -> str:
    return f"{car.get('model') or ''} {car.get('title') or ''}".strip()


def _ts(s: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(s) if s else None
    except ValueError:
        return None


def passes_filter(car: dict, vin: str, favorites: set, flt: dict) -> bool:
    """Alert filter. Favorites always pass."""
    if vin in favorites:
        return True
    max_price = flt.get("max_price") or 0
    if max_price and car.get("price") is not None and car["price"] > max_price:
        return False
    max_km = flt.get("max_km") or 0
    km = car.get("mileage_km")
    if max_km and km is not None and km > max_km:
        return False
    if not flt.get("include_demo", True) and car.get("is_demo"):
        return False
    return True


def _summary(car: dict) -> str:
    parts = [fmt_eur(car.get("price"))]
    if car.get("battery_kwh"):
        parts.append(f"{car['battery_kwh']} kWh")
    if car.get("is_demo"):
        km = car.get("mileage_km")
        parts.append("predvádzacie" + (f", {km:,} km".replace(",", "\u00a0") if km else ""))
    if car.get("dealer_city"):
        parts.append(car["dealer_city"])
    return " · ".join(parts)


def _text(kind: str, car: dict, extra: dict) -> tuple[str, str]:
    name = label(car)
    if kind == EVT_NEW:
        head = "Znovu v ponuke" if extra.get("returned") else "Nová ponuka"
        return f"{head}: {name}", _summary(car)
    if kind in (EVT_DROP, EVT_RISE):
        head = "Zníženie ceny" if kind == EVT_DROP else "Zvýšenie ceny"
        sign = "−" if extra["diff"] < 0 else "+"
        msg = (f"{fmt_eur(extra['old_price'])} → {fmt_eur(extra['new_price'])} "
               f"({sign}{fmt_eur(abs(extra['diff']))}) · {car.get('dealer_city') or ''}")
        return f"{head}: {name}", msg
    if kind == EVT_RESERVED:
        return f"Rezervované: {name}", _summary(car)
    if kind == EVT_UNRESERVED:
        return f"Rezervácia zrušená: {name}", _summary(car)
    if kind == EVT_REMOVED:
        why = "bolo rezervované, pravdepodobne predané" if extra.get("was_reserved") else "stiahnuté z ponuky"
        return f"Preč z ponuky: {name}", f"{fmt_eur(car.get('price'))} · {why}"
    return name, ""


def payload(kind: str, vin: str, car: dict, link_fn: Callable[[dict], str], **extra: Any) -> dict:
    title, message = _text(kind, car, extra)
    return {
        "vin": vin, "title": title, "message": message,
        "car": label(car), "price": car.get("price"), "list_price": car.get("list_price"),
        "is_demo": car.get("is_demo"), "is_reserved": car.get("is_reserved"),
        "mileage_km": car.get("mileage_km"), "dealer": car.get("dealer_name"),
        "city": car.get("dealer_city"), "url": link_fn(car), "image": car.get("image_large") or car.get("image"),
        **extra,
    }


def apply_update(db: dict, current: dict[str, dict], models: list[str], now: str,
                 flt: dict, link_fn: Callable[[dict], str]) -> list[tuple[str, dict]]:
    """Merge a complete fetch into db. Returns [(event_type, payload)]."""
    cars = db["cars"]
    favs = set(db.get("favorites", []))
    first_run = not db.get("initialized")
    events: list[tuple[str, dict]] = []

    def emit(kind: str, vin: str, car: dict, **extra: Any) -> None:
        if passes_filter(car, vin, favs, flt):
            events.append((kind, payload(kind, vin, car, link_fn, **extra)))

    for vin, car in current.items():
        price = car.get("price")
        rec = cars.get(vin)
        if rec is None:
            cars[vin] = {
                "first_seen": now, "last_seen": now, "baseline": first_run,
                "missing": 0, "removed_at": None,
                "reserved_since": now if car.get("is_reserved") else None,
                "price_history": [[now, price]] if price is not None else [],
                "car": car,
            }
            if not first_run:
                emit(EVT_NEW, vin, car)
            continue

        hist = rec["price_history"]
        last = hist[-1][1] if hist else None
        returned = bool(rec.get("removed_at"))
        old_reserved = bool(rec["car"].get("is_reserved"))
        rec["missing"] = 0
        rec["last_seen"] = now
        rec["removed_at"] = None

        changed = price is not None and price != last
        if changed:
            hist.append([now, price])
            del hist[:-HISTORY_MAX]

        if returned:
            emit(EVT_NEW, vin, car, returned=True)
        elif changed and last is not None:
            emit(EVT_DROP if price < last else EVT_RISE, vin, car,
                 old_price=last, new_price=price, diff=price - last)

        now_reserved = bool(car.get("is_reserved"))
        if now_reserved != old_reserved:
            rec["reserved_since"] = now if now_reserved else None
            emit(EVT_RESERVED if now_reserved else EVT_UNRESERVED, vin, car)
        rec["car"] = car

    for vin, rec in cars.items():
        if vin in current or rec.get("removed_at"):
            continue
        if rec["car"].get("model_code") not in models:
            continue
        rec["missing"] = rec.get("missing", 0) + 1
        if rec["missing"] >= MISSING_THRESHOLD:
            rec["removed_at"] = now
            emit(EVT_REMOVED, vin, rec["car"], was_reserved=bool(rec["car"].get("is_reserved")))

    cutoff = _ts(now) - timedelta(days=PURGE_DAYS)  # type: ignore[operator]
    for vin in [v for v, r in cars.items()
                if r.get("removed_at") and v not in favs
                and (_ts(r["removed_at"]) or cutoff) < cutoff]:
        del cars[vin]

    db["initialized"] = True
    return events


def price_change(rec: dict) -> tuple[float | None, str | None]:
    """(previous price, when it changed) from history."""
    hist = rec.get("price_history") or []
    if len(hist) >= 2:
        return hist[-2][1], hist[-1][0]
    return None, None


def car_view(vin: str, rec: dict, favs: set, link_fn: Callable[[dict], str]) -> dict:
    car = rec["car"]
    prev, changed_at = price_change(rec)
    return {
        **car, "url": link_fn(car), "favorite": vin in favs,
        "first_seen": rec.get("first_seen"), "last_seen": rec.get("last_seen"),
        "removed_at": rec.get("removed_at"), "baseline": rec.get("baseline", False),
        "reserved_since": rec.get("reserved_since"),
        "price_prev": prev, "price_changed_at": changed_at,
        "price_history": rec.get("price_history") or [],
        "packages": (rec.get("equipment") or {}).get("packages"),
        "ft": (rec.get("equipment") or {}).get("features"),
        "tech": (rec.get("equipment") or {}).get("tech"),
    }


def _brief(vin: str, car: dict, link_fn: Callable[[dict], str], **extra: Any) -> dict:
    return {"vin": vin, "car": label(car), "price": car.get("price"),
            "city": car.get("dealer_city"), "reserved": car.get("is_reserved"),
            "demo": car.get("is_demo"), "url": link_fn(car), **extra}


def compute_stats(db: dict, now: datetime, link_fn: Callable[[dict], str]) -> dict:
    favs = set(db.get("favorites", []))
    day = now - timedelta(days=1)
    cars = db["cars"]
    active = {v: r for v, r in cars.items() if not r.get("removed_at")}

    by_model: dict[str, int] = {}
    for r in active.values():
        m = r["car"].get("model") or "?"
        by_model[m] = by_model.get(m, 0) + 1

    priced = [(v, r) for v, r in active.items() if r["car"].get("price") is not None]
    cheapest = None
    if priced:
        v, r = min(priced, key=lambda x: x[1]["car"]["price"])
        cheapest = _brief(v, r["car"], link_fn)

    new24, drops24, fav_changed = [], [], []
    for v, r in active.items():
        fs = _ts(r.get("first_seen"))
        if not r.get("baseline") and fs and fs >= day:
            new24.append(_brief(v, r["car"], link_fn))
        prev, when = price_change(r)
        wt = _ts(when)
        dropped = prev is not None and wt and wt >= day and r["car"]["price"] < prev
        if dropped:
            drops24.append(_brief(v, r["car"], link_fn, old_price=prev))
        if v in favs:
            rs = _ts(r.get("reserved_since"))
            if (prev is not None and wt and wt >= day) or (rs and rs >= day):
                fav_changed.append(_brief(v, r["car"], link_fn))
    for v in favs:
        r = cars.get(v)
        ra = _ts(r.get("removed_at")) if r else None
        if r and ra and ra >= day:
            fav_changed.append(_brief(v, r["car"], link_fn, removed=True))

    return {
        "total": len(active), "by_model": by_model, "cheapest": cheapest,
        "new24": new24, "drops24": drops24,
        "reserved": sum(1 for r in active.values() if r["car"].get("is_reserved")),
        "demo": sum(1 for r in active.values() if r["car"].get("is_demo")),
        "favorites": [_brief(v, cars[v]["car"], link_fn, removed=bool(cars[v].get("removed_at")))
                      for v in favs if v in cars],
        "favorites_changed": fav_changed,
        "updated_at": now,
    }


# ---------------------------------------------------------------- equipment
TECH_KEYS = (
    "ElectricCarBatteryCapacity", "MaximumDcChargingPower", "BatteryChargingTime80_SOC_Max_DC",
    "BatteryChargingTimeAC11_100_SOC", "Acceleration", "MaxSpeed", "LuggageCapacity",
    "TowingWeightBraked12", "Payload.WithDriver",
)


def _clean(text: Any) -> str:
    return " ".join(str(text or "").split())


def _feature_id(item: dict) -> str | None:
    """Option code if present (unique per option), else family+text (standard equipment)."""
    code = _clean(item.get("keytoolCode"))
    if code:
        return code
    fam, text = _clean(item.get("family")), _clean(item.get("text"))
    return f"{fam}:{text}" if (fam or text) else None


def parse_equipment(data: Any) -> tuple[dict, dict] | None:
    """getCarDetail response -> (equipment, catalog) or None if it has no equipment."""
    if isinstance(data, dict) and isinstance(data.get("results"), dict):
        data = data["results"]
    groups = data.get("equipmentGroups") if isinstance(data, dict) else None
    if not isinstance(groups, list) or not groups:
        return None

    catalog: dict[str, dict] = {}
    features: list[str] = []
    seen: set[str] = set()
    packages: list[dict] = []
    tech: dict[str, str] = {}

    def add(item: dict, group: str) -> str | None:
        fid, text = _feature_id(item), _clean(item.get("text"))
        if not fid or not text:
            return None
        catalog.setdefault(fid, {"t": text, "g": group})
        return fid

    def keep(fid: str | None) -> None:
        if fid and fid not in seen:
            seen.add(fid)
            features.append(fid)

    for g in groups:
        gid = g.get("id")
        if gid == "packages":
            for sec in g.get("sections") or []:
                ids = [x for x in (add(i, "Balíky") for i in sec.get("items") or []) if x]
                packages.append({"t": _clean(sec.get("title")) or "Balík", "f": ids})
            continue
        if gid == "tech_equip":
            for sec in g.get("sections") or []:
                for it in sec.get("items") or []:
                    if it.get("key") in TECH_KEYS and it.get("text"):
                        tech[it["key"]] = _clean(it["text"])
            continue
        group = _clean(g.get("name"))
        for it in (g.get("items") or []) + (g.get("itemsSpecial") or []):
            keep(add(it, group))
    for pkg in packages:
        for fid in pkg["f"]:
            keep(fid)
    return {"packages": packages, "features": features, "tech": tech}, catalog


def merge_equipment(db: dict, vin: str, equipment: dict, catalog: dict, now: str) -> None:
    db.setdefault("catalog", {})
    for fid, meta in catalog.items():
        db["catalog"].setdefault(fid, meta)
    rec = db["cars"][vin]
    rec["equipment"] = equipment
    rec["equip_at"] = now


def missing_equipment(db: dict, now: str, retry_hours: float, limit: int | None = None) -> list[str]:
    """Active cars without equipment whose last attempt is absent or old enough."""
    cutoff = _ts(now) - timedelta(hours=retry_hours)  # type: ignore[operator]
    out = []
    for vin, rec in sorted(db["cars"].items(), key=lambda kv: kv[1]["car"].get("order", 0)):
        if rec.get("removed_at") or rec.get("equipment"):
            continue
        last = _ts(rec.get("equip_attempt"))
        if last is None or last < cutoff:
            out.append(vin)
    return out[:limit] if limit else out


def used_catalog(db: dict) -> dict:
    ids: set[str] = set()
    for rec in db["cars"].values():
        eq = rec.get("equipment")
        if eq and not rec.get("removed_at"):
            ids.update(eq["features"])
    cat = db.get("catalog", {})
    return {i: cat[i] for i in ids if i in cat}
