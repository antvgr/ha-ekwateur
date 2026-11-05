from datetime import date

from ekw.parser import parse_bills, parse_date, parse_meter_readings, parse_tariff


def test_parse_date_formats():
    assert parse_date("2026-11-03T23:00:00Z") == date(2026, 11, 4)  # minuit à Paris
    assert parse_date("04/11/2026") == date(2026, 11, 4)
    assert parse_date(1793750400000) == date(2026, 11, 4)
    assert parse_date(None) is None


def test_meter_readings_base():
    raw = {"ELEC": [{"meterType": "CCB", "pricing": "BASE", "readings": [
        {"readingDate": "2026-10-04", "indexReadings": [{"endIndex": 10500, "temporalCategory": "BASE"}]},
        {"readingDate": "2026-11-04", "nextReadingDate": "2026-11-16", "origin": "ENEDIS",
         "indexReadings": [{"endIndex": 10782, "temporalCategory": "BASE"}]},
    ]}], "GAZ": []}
    m = parse_meter_readings(raw)
    assert m["indexes"] == {"base": 10782.0}
    assert m["reading_date"] == date(2026, 11, 4)
    assert m["next_reading_date"] == date(2026, 11, 16)


def test_meter_readings_hphc():
    raw = {"ELEC": [{"readings": [{"readingDate": "2026-11-04", "indexReadings": [
        {"endIndex": 100, "temporalCategory": "HP"}, {"endIndex": 50, "temporalCategory": "HC"}]}]}]}
    assert parse_meter_readings(raw)["indexes"] == {"hp": 100.0, "hc": 50.0}


def test_bills():
    raw = {"fees": [{"amount": 47, "dueDate": "2026-12-05"}], "billsUnpaid": [],
           "billsList": [{"amount": 47, "dueDate": "2026-10-29", "type": "MEN", "payment": {"status": "PAID"}}],
           "billingRate": "ANN", "nextMonthlyFee": {"amount": 47, "dueDate": "2026-12-05"}}
    b = parse_bills(raw)
    assert b["next_fee_amount"] == 47 and b["next_fee_date"] == date(2026, 12, 5)
    assert b["last_bill_status"] == "PAID"


def test_tariff_current_period():
    raw = {"tariffOptions": [{"energy": "ELEC", "current": {"type": "FIXE", "name": "Fixe", "pricePeriods": [
        {"startDate": "2025-11-04", "endDate": "2026-11-04", "base": 0.2, "subscription": 15.0},
        {"startDate": "2026-11-04", "endDate": "2027-11-04", "base": 0.1753, "subscription": 15.86},
    ]}}]}
    t = parse_tariff(raw, date(2026, 11, 5))
    assert t["price_base"] == 0.1753 and t["subscription"] == 15.86
