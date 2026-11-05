"""Constantes de l'intégration Ekwateur."""
from datetime import timedelta

DOMAIN = "ekwateur"

API_BASE = "https://api-ec.ekwateur.fr"
WEB_ORIGIN = "https://mon-espace.ekwateur.fr"

# Endpoints observés dans l'espace client mon-espace.ekwateur.fr
EP_USER_INFO = "/dashboard/user-information"
EP_METERS_READINGS = "/v2/meters-readings/{ref}"
EP_BILLS_HISTORY = "/v3/my_profile/bills_history/{ref}"
EP_TARIFF_OPTIONS = "/billing/tariff-options/{ref}"
EP_REFRESH = "/refresh_token"

# Clés de l'entrée de configuration
CONF_CREDENTIALS = "credentials"  # champ du formulaire
CONF_ACCESS_TOKEN = "access_token"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_USERNAME = "username"
CONF_CUSTOMER_REF = "customer_reference"

DEFAULT_SCAN_INTERVAL = timedelta(hours=3)
# L'AccessToken dure 24 h : on le renouvelle dès qu'il reste moins de 4 h
REFRESH_MARGIN = timedelta(hours=4)
