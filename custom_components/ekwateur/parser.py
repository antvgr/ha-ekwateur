"""Normalisation des réponses de l'API Ekwateur (sans dépendance à Home Assistant)."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")

# Catégories temporelles Enedis/Ekwateur -> clé courte
TEMPORAL_KEYS = {
    "BASE": "base",
    "HP": "hp",
    "HC": "hc",
    "HPH": "hph",
    "HCH": "hch",
    "HPB": "hpb",
    "HCB": "hcb",
}


def parse_date(value: Any) -> date | None:
    """Accepte ISO (2026-11-04 / 2026-11-04T00:00:00Z), JJ/MM/AAAA ou timestamp."""
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)):
        ts = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(ts, tz=timezone.utc).date()
    if isinstance(value, str):
        s = value.strip()
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            if dt.tzinfo is not None:
                dt = dt.astimezone(PARIS)
            return dt.date()
        except ValueError:
            pass
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
            try:
                return datetime.strptime(s[:10], fmt).date()
            except ValueError:
                continue
    return None


def _elec_meters(raw: Any) -> list[dict]:
    """La réponse peut être {"ELEC": [...], "GAZ": [...]} ou une liste."""
    if isinstance(raw, dict):
        for key in ("ELEC", "elec", "electricity", "ELECTRICITY"):
            if isinstance(raw.get(key), list):
                return raw[key]
        if isinstance(raw.get("data"), (dict, list)):
            return _elec_meters(raw["data"])
        return []
    if isinstance(raw, list):
        return [
            m
            for m in raw
            if str(m.get("energy", m.get("energyType", "ELEC"))).upper().startswith("ELEC")
        ]
    return []


def parse_meter_readings(raw: Any) -> dict:
    """Retourne la dernière relève électricité avec ses index par cadran."""
    result: dict = {"indexes": {}}
    meters = _elec_meters(raw)
    if not meters:
        return result

    meter = meters[0]
    result["meter_type"] = meter.get("meterType")
    result["pricing"] = meter.get("pricing")
    result["provider"] = meter.get("providerName")

    readings = [r for r in (meter.get("readings") or []) if parse_date(r.get("readingDate"))]
    if not readings:
        return result
    last = max(readings, key=lambda r: parse_date(r.get("readingDate")))

    result["reading_date"] = parse_date(last.get("readingDate"))
    result["next_reading_date"] = parse_date(last.get("nextReadingDate"))
    result["origin"] = last.get("origin")
    result["reading_type"] = last.get("endReadingType")
    result["reading_status"] = last.get("endReadingStatus")
    result["reading_reason"] = last.get("endReadingReason")

    for idx in last.get("indexReadings") or []:
        cat = str(idx.get("temporalCategory") or "BASE").upper()
        key = TEMPORAL_KEYS.get(cat, cat.lower())
        value = idx.get("endIndex", idx.get("startIndex"))
        if value is not None:
            result["indexes"][key] = float(value)
    return result


def parse_bills(raw: dict) -> dict:
    """Prochaine mensualité + dernière facture/échéance payée."""
    raw = raw or {}
    out: dict = {"billing_rate": raw.get("billingRate")}

    nxt = raw.get("nextMonthlyFee")
    if not nxt:
        today = date.today()
        future = [f for f in raw.get("fees") or [] if (parse_date(f.get("dueDate")) or date.min) >= today]
        nxt = min(future, key=lambda f: parse_date(f.get("dueDate"))) if future else None
    if nxt:
        out["next_fee_amount"] = nxt.get("amount")
        out["next_fee_date"] = parse_date(nxt.get("dueDate"))

    fees = raw.get("fees") or []
    out["fees_schedule"] = [
        {"date": d.isoformat(), "amount": f.get("amount")}
        for f in fees
        if (d := parse_date(f.get("dueDate")))
    ]

    bills = [b for b in raw.get("billsList") or [] if parse_date(b.get("dueDate"))]
    if bills:
        last = max(bills, key=lambda b: parse_date(b.get("dueDate")))
        out["last_bill_amount"] = last.get("amount")
        out["last_bill_date"] = parse_date(last.get("dueDate"))
        out["last_bill_type"] = last.get("type")
        out["last_bill_status"] = (last.get("payment") or {}).get("status")
    out["unpaid_count"] = len(raw.get("billsUnpaid") or [])
    return out


def parse_tariff(raw: dict, today: date | None = None) -> dict:
    """Prix du kWh (€/kWh TTC) et abonnement (€/mois) de la période en cours."""
    today = today or date.today()
    out: dict = {}
    options = (raw or {}).get("tariffOptions") or []
    elec = next((o for o in options if str(o.get("energy", "")).upper().startswith("ELEC")), None)
    if not elec:
        return out
    current = elec.get("current") or {}
    out["offer_type"] = current.get("type")
    out["offer_name"] = current.get("name")

    periods = current.get("pricePeriods") or []
    period = None
    for p in periods:
        start, end = parse_date(p.get("startDate")), parse_date(p.get("endDate"))
        if (start is None or start <= today) and (end is None or today < end):
            period = p
            break
    if period is None and periods:
        period = periods[-1]
    if period:
        out["price_base"] = period.get("base")
        out["price_hp"] = period.get("high")
        out["price_hc"] = period.get("low")
        out["subscription"] = period.get("subscription")
        out["period_start"] = parse_date(period.get("startDate"))
        out["period_end"] = parse_date(period.get("endDate"))

    nxt = elec.get("next")
    if isinstance(nxt, dict):
        out["next_offer_name"] = nxt.get("name")
    return out
