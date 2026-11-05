"""Capteurs Ekwateur."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import CURRENCY_EURO, EntityCategory, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import EkwateurConfigEntry
from .const import DOMAIN
from .coordinator import EkwateurCoordinator

INDEX_LABELS = {
    "base": "Index électricité",
    "hp": "Index heures pleines",
    "hc": "Index heures creuses",
}


@dataclass(frozen=True, kw_only=True)
class EkwSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict], Any]
    attrs_fn: Callable[[dict], dict] | None = None
    exists_fn: Callable[[dict], bool] = lambda d: True
    # Valeur lue sur le coordinateur plutôt que dans les données (ex. prochaine actualisation)
    coordinator_fn: Callable[[EkwateurCoordinator], Any] | None = None


def _meter_attrs(d: dict) -> dict:
    m = d["meter"]
    return {
        "date_releve": m.get("reading_date").isoformat() if m.get("reading_date") else None,
        "prochaine_releve": m.get("next_reading_date").isoformat() if m.get("next_reading_date") else None,
        "origine": m.get("origin"),
        "type_releve": m.get("reading_type"),
        "option_tarifaire": m.get("pricing"),
        "type_compteur": m.get("meter_type"),
    }


def _static_descriptions() -> list[EkwSensorDescription]:
    return [
        # --- Relève ---
        EkwSensorDescription(
            key="reading_date",
            name="Date de la dernière relève",
            icon="mdi:calendar-check",
            device_class=SensorDeviceClass.DATE,
            value_fn=lambda d: d["meter"].get("reading_date"),
            attrs_fn=lambda d: {"origine": d["meter"].get("origin")},
        ),
        EkwSensorDescription(
            key="next_reading_date",
            name="Date de la prochaine relève",
            icon="mdi:calendar-clock",
            device_class=SensorDeviceClass.DATE,
            value_fn=lambda d: d["meter"].get("next_reading_date"),
        ),
        # --- Mensualités ---
        EkwSensorDescription(
            key="next_fee_amount",
            name="Prochaine mensualité",
            icon="mdi:cash-clock",
            device_class=SensorDeviceClass.MONETARY,
            native_unit_of_measurement=CURRENCY_EURO,
            suggested_display_precision=2,
            value_fn=lambda d: d["bills"].get("next_fee_amount"),
            attrs_fn=lambda d: {
                "date_prelevement": d["bills"]["next_fee_date"].isoformat()
                if d["bills"].get("next_fee_date")
                else None,
                "rythme_facturation": d["bills"].get("billing_rate"),
                "echeancier": d["bills"].get("fees_schedule"),
            },
        ),
        EkwSensorDescription(
            key="next_fee_date",
            name="Date du prochain prélèvement",
            icon="mdi:calendar-arrow-right",
            device_class=SensorDeviceClass.DATE,
            value_fn=lambda d: d["bills"].get("next_fee_date"),
        ),
        EkwSensorDescription(
            key="last_bill_amount",
            name="Dernier montant facturé",
            icon="mdi:receipt-text",
            device_class=SensorDeviceClass.MONETARY,
            native_unit_of_measurement=CURRENCY_EURO,
            suggested_display_precision=2,
            entity_category=EntityCategory.DIAGNOSTIC,
            value_fn=lambda d: d["bills"].get("last_bill_amount"),
            attrs_fn=lambda d: {
                "date": d["bills"]["last_bill_date"].isoformat() if d["bills"].get("last_bill_date") else None,
                "type": d["bills"].get("last_bill_type"),
                "statut": d["bills"].get("last_bill_status"),
                "impayes": d["bills"].get("unpaid_count"),
            },
            exists_fn=lambda d: d["bills"].get("last_bill_amount") is not None,
        ),
        # --- Tarifs ---
        EkwSensorDescription(
            key="price_base",
            name="Prix du kWh",
            icon="mdi:currency-eur",
            native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
            suggested_display_precision=4,
            value_fn=lambda d: d["tariff"].get("price_base"),
            attrs_fn=lambda d: {
                "offre": d["tariff"].get("offer_name"),
                "type_offre": d["tariff"].get("offer_type"),
                "debut": d["tariff"]["period_start"].isoformat() if d["tariff"].get("period_start") else None,
                "fin": d["tariff"]["period_end"].isoformat() if d["tariff"].get("period_end") else None,
            },
            exists_fn=lambda d: d["tariff"].get("price_base") is not None,
        ),
        EkwSensorDescription(
            key="price_hp",
            name="Prix du kWh heures pleines",
            icon="mdi:currency-eur",
            native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
            suggested_display_precision=4,
            value_fn=lambda d: d["tariff"].get("price_hp"),
            exists_fn=lambda d: d["tariff"].get("price_hp") is not None,
        ),
        EkwSensorDescription(
            key="price_hc",
            name="Prix du kWh heures creuses",
            icon="mdi:currency-eur",
            native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
            suggested_display_precision=4,
            value_fn=lambda d: d["tariff"].get("price_hc"),
            exists_fn=lambda d: d["tariff"].get("price_hc") is not None,
        ),
        EkwSensorDescription(
            key="subscription",
            name="Prix de l'abonnement",
            icon="mdi:file-sign",
            native_unit_of_measurement=f"{CURRENCY_EURO}/mois",
            suggested_display_precision=2,
            value_fn=lambda d: d["tariff"].get("subscription"),
            attrs_fn=lambda d: {"offre": d["tariff"].get("offer_name")},
            exists_fn=lambda d: d["tariff"].get("subscription") is not None,
        ),
        EkwSensorDescription(
            key="token_expires",
            name="Jeton expire le",
            icon="mdi:key-chain",
            device_class=SensorDeviceClass.TIMESTAMP,
            entity_category=EntityCategory.DIAGNOSTIC,
            value_fn=lambda d: d.get("token_expires"),
        ),
        EkwSensorDescription(
            key="next_refresh",
            name="Prochaine actualisation",
            icon="mdi:timer-sand",
            device_class=SensorDeviceClass.TIMESTAMP,
            entity_category=EntityCategory.DIAGNOSTIC,
            value_fn=lambda d: None,
            coordinator_fn=lambda c: c.next_refresh,
        ),
        EkwSensorDescription(
            key="offer",
            name="Offre",
            icon="mdi:tag-text",
            entity_category=EntityCategory.DIAGNOSTIC,
            value_fn=lambda d: d["tariff"].get("offer_name"),
            attrs_fn=lambda d: {
                "type": d["tariff"].get("offer_type"),
                "fin_periode": d["tariff"]["period_end"].isoformat() if d["tariff"].get("period_end") else None,
                "offre_suivante": d["tariff"].get("next_offer_name"),
            },
        ),
    ]


def _index_descriptions(data: dict) -> list[EkwSensorDescription]:
    out = []
    for key in data["meter"].get("indexes", {}):
        out.append(
            EkwSensorDescription(
                key=f"index_{key}",
                name=INDEX_LABELS.get(key, f"Index {key.upper()}"),
                icon="mdi:counter",
                device_class=SensorDeviceClass.ENERGY,
                state_class=SensorStateClass.TOTAL_INCREASING,
                native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
                suggested_display_precision=0,
                value_fn=lambda d, k=key: d["meter"].get("indexes", {}).get(k),
                attrs_fn=_meter_attrs,
            )
        )
    return out


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EkwateurConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    data = coordinator.data
    descriptions = _index_descriptions(data) + _static_descriptions()
    async_add_entities(
        EkwateurSensor(coordinator, desc) for desc in descriptions if desc.exists_fn(data)
    )


class EkwateurSensor(CoordinatorEntity[EkwateurCoordinator], SensorEntity):
    _attr_has_entity_name = True
    entity_description: EkwSensorDescription

    def __init__(self, coordinator: EkwateurCoordinator, description: EkwSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.ref}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.ref)},
            name=f"Ekwateur {coordinator.ref}",
            manufacturer="Ekwateur",
            model="Contrat électricité",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://mon-espace.ekwateur.fr/",
        )

    @property
    def native_value(self) -> Any:
        desc = self.entity_description
        if desc.coordinator_fn is not None:
            return desc.coordinator_fn(self.coordinator)
        return desc.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict | None:
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator.data)
