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

# Client Cognito public de l'espace client (visible dans le claim client_id du JWT).
# Utilisé seulement si l'utilisateur ne fournit qu'un RefreshToken.
DEFAULT_COGNITO_CLIENT_ID = "2e7f4abigi7k3vnkp0ssn4nhuf"
DEFAULT_COGNITO_REGION = "eu-west-1"

# Clés de l'entrée de configuration
CONF_CREDENTIALS = "credentials"  # champ du formulaire
CONF_ACCESS_TOKEN = "access_token"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_USERNAME = "username"
CONF_COGNITO_CLIENT_ID = "cognito_client_id"
CONF_COGNITO_REGION = "cognito_region"
CONF_CUSTOMER_REF = "customer_reference"

DEFAULT_SCAN_INTERVAL = timedelta(hours=3)
# L'AccessToken dure 24 h : on le renouvelle dès qu'il reste moins de 4 h
REFRESH_MARGIN = timedelta(hours=4)
