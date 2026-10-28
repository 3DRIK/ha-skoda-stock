"""Škoda stock API client + normalisation."""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any
from urllib.parse import quote

import aiohttp

from .const import API_URL, LIST_URL, MAX_PAGES, PAGE_DELAY, USER_AGENT

_LOGGER = logging.getLogger(__name__)
HEADERS = {"Accept": "application/json;profile=camelcase", "User-Agent": USER_AGENT}


class SkodaStockError(Exception):
    """API error."""


def _num(value: Any) -> float | None:
    if value is None:
        return None
    cleaned = re.sub(r"[^\d,.\-]", "", str(value)).replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _walk_value(block: dict | None, key: str) -> float | None:
    for cat in (block or {}).get("engineCategorizationItems") or []:
        for std in cat.get("testStandardCategorizationItems") or []:
            for fuel in std.get("fuelItems") or []:
                for val in fuel.get("values") or []:
                    if val.get("key") == key:
                        return _num(val.get("value"))
    return None


def normalize(raw: dict, order: int = 0) -> dict | None:
    """Flatten one raw car into the fields we use."""
    vin = raw.get("vin")
    if not vin:
        return None
    sale = (raw.get("salePrice") or {}).get("value")
    listp = (raw.get("listPrice") or {}).get("value")
    price = sale if sale is not None else listp
    tech = raw.get("technicalData") or {}
    dealer = raw.get("dealer") or {}
    colors = raw.get("colors") or {}
    images = raw.get("images") or {}
    battery = re.search(r"(\d+)\s*kWh", tech.get("engineShortName") or tech.get("engineName") or "")
    mileage = _num((raw.get("mileage") or {}).get("value"))
    diff = (raw.get("differencePrice") or {}).get("value")
    if diff is None and price is not None and listp is not None:
        diff = listp - price
    return {
        "vin": vin,
        "id": raw.get("id"),
        "key": raw.get("key"),
        "commission": raw.get("commisionNumber"),
        "order": order,
        "model": raw.get("model") or raw.get("marketingName"),
        "model_code": raw.get("modelCode"),
        "marketing_name": raw.get("marketingName"),
        "title": raw.get("title") or raw.get("subTitle"),
        "model_year": raw.get("modelYear"),
        "price": price,
        "list_price": listp,
        "discount": diff,
        "mileage_km": int(mileage) if mileage is not None else None,
        "is_demo": bool(raw.get("isDemoCar")) or raw.get("businessModel") == "demo_car",
        "is_reserved": bool(raw.get("isReserved")),
        "business_model": raw.get("businessModel"),
        "battery_kwh": int(battery.group(1)) if battery else None,
        "power_kw": (tech.get("motor") or {}).get("value"),
        "drive": tech.get("drive"),
        "color": (colors.get("exterior") or {}).get("text"),
        "interior": (colors.get("interior") or {}).get("text") or None,
        "range_km": _walk_value(raw.get("range"), "COMBINED"),
        "consumption": _walk_value(raw.get("consumption"), "COMBINED"),
        "production_date": (raw.get("productionDate") or "")[:10] or None,
        "initial_reg": raw.get("initialReg") if raw.get("initialReg") not in (None, "without") else None,
        "available_from": raw.get("availableFrom"),
        "dealer_id": dealer.get("id"),
        "dealer_name": dealer.get("name"),
        "dealer_city": dealer.get("city"),
        "dealer_phone": dealer.get("telephone"),
        "dealer_email": dealer.get("email"),
        "dealer_website": dealer.get("website"),
        "image": raw.get("image") or images.get("ExteriorFrontSmall"),
        "image_large": images.get("ExteriorFrontLarge"),
    }


def build_link(car: dict, template: str | None) -> str:
    """Link to the car on skoda-auto.sk (template configurable), else filtered list."""
    if template:
        try:
            return template.format(
                key=quote(str(car.get("key") or ""), safe=""),
                id=car.get("id") or "",
                vin=car.get("vin") or "",
                commission=car.get("commission") or "",
                model_code=car.get("model_code") or "",
            )
        except (KeyError, IndexError, ValueError):
            _LOGGER.warning("Invalid link template: %s", template)
    return (
        f"{LIST_URL}?Model={car.get('model_code') or ''}"
        "&Sort=DATE_OFFER&SortDirection=DESC"
    )


async def fetch_page(session: aiohttp.ClientSession, models: list[str], page: int) -> dict:
    params = [("CarType", "N")] + [("Model", m) for m in models] + [
        ("PageNo", str(page)), ("SortDirection", "1"), ("SortKey", "DATE_OFFER"),
    ]
    last_err: Exception | None = None
    for attempt in range(2):
        try:
            async with session.get(
                API_URL, params=params, headers=HEADERS,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    raise SkodaStockError(f"HTTP {resp.status}")
                return await resp.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError, SkodaStockError) as err:
            last_err = err
            await asyncio.sleep(3)
    raise SkodaStockError(f"page {page}: {last_err}")


async def fetch_all(session: aiohttp.ClientSession, models: list[str]) -> dict[str, dict]:
    """Fetch every page; raise if the result looks incomplete."""
    first = await fetch_page(session, models, 1)
    results = first.get("results") or {}
    info = results.get("pageInfo") or {}
    page_count = int(info.get("pageCount") or 1)
    total = info.get("resultsCount")
    raw = list(results.get("cars") or [])
    for page in range(2, min(page_count, MAX_PAGES) + 1):
        await asyncio.sleep(PAGE_DELAY)
        data = await fetch_page(session, models, page)
        raw.extend((data.get("results") or {}).get("cars") or [])
    cars: dict[str, dict] = {}
    for i, item in enumerate(raw):
        car = normalize(item, i)
        if car and car["vin"] not in cars:
            cars[car["vin"]] = car
    if isinstance(total, int) and total > 0 and len(cars) < total * 0.9:
        raise SkodaStockError(f"incomplete result: {len(cars)}/{total}")
    return cars
