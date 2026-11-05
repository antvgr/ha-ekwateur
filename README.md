# Ekwateur pour Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)
[![Validate](https://github.com/antvgr/ha-ekwateur/actions/workflows/validate.yml/badge.svg)](https://github.com/antvgr/ha-ekwateur/actions/workflows/validate.yml)
[![Release](https://img.shields.io/github/v/release/antvgr/ha-ekwateur)](https://github.com/antvgr/ha-ekwateur/releases)

Intégration **non officielle** (sans lien avec Ekwateur) qui récupère depuis l'espace client `mon-espace.ekwateur.fr` :

| Entité | Unité | Détail |
|---|---|---|
| Index électricité (ou HP / HC) | kWh | `total_increasing`, attributs : date de relève, prochaine relève, origine (ENEDIS / auto-relève) |
| Date de la dernière relève / de la prochaine | date | |
| Prochaine mensualité | € | attributs : date de prélèvement, échéancier complet |
| Date du prochain prélèvement | date | |
| Prix du kWh (Base, ou HP / HC) | €/kWh | période de prix en cours |
| Prix de l'abonnement | €/mois | |
| Offre | texte | type (FIXE…), fin de période |
| Dernier montant facturé | € | diagnostic |
| Jeton expire le | horodatage | diagnostic : doit avancer tout seul |
| Prochaine actualisation | horodatage | diagnostic : heure de la prochaine interrogation de l'API (toutes les 3 h), affichée « dans X heures » |

## Installation

### Via HACS (recommandé)

[![Ouvrir dans HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=antvgr&repository=ha-ekwateur&category=integration)

1. HACS → menu ⋮ → **Dépôts personnalisés** → `https://github.com/antvgr/ha-ekwateur`, catégorie **Intégration**.
2. Installer **Ekwateur**, puis redémarrer Home Assistant.
3. [![Ajouter l'intégration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=ekwateur)

### Manuelle

Copier `custom_components/ekwateur` dans `config/custom_components/`, redémarrer, puis Paramètres → Appareils et services → Ajouter → **Ekwateur**.

## Pourquoi pas de champ identifiant / mot de passe ?

La connexion Ekwateur exige un captcha (Cloudflare Turnstile). L'intégration ne le contourne pas : vous vous connectez vous-même une fois, puis elle renouvelle la session automatiquement.

## Authentification

La connexion Ekwateur est protégée par un captcha : **c'est vous qui vous connectez** sur le site, une fois. La réponse de connexion contient :

- `AccessToken` : valable 24 h ;
- `RefreshToken` : longue durée (durée fixée par Ekwateur).

L'intégration renouvelle l'AccessToken toute seule avec le RefreshToken (vérification toutes les 3 h), via l'endpoint Ekwateur `/refresh_token`. Les jetons renouvelés sont sauvegardés. Quand le RefreshToken finit par expirer, Home Assistant affiche « Réauthentification requise » : il suffit de refaire l'étape ci-dessous depuis votre téléphone.

### Favori « Jetons Ekwateur » (fonctionne sur téléphone)

Créez un favori nommé `Jetons Ekwateur` avec cette URL :

```
javascript:(()=>{const show=j=>{if(!j||!j.RefreshToken)return;const s=JSON.stringify({AccessToken:j.AccessToken,RefreshToken:j.RefreshToken,Username:j.Username});navigator.clipboard.writeText(s).then(()=>alert('Jetons Ekwateur copiés, collez-les dans Home Assistant'),()=>prompt('Copiez ce texte dans Home Assistant :',s));};const isAuth=u=>/api-ec\.ekwateur\.fr\/auth(\?|$)/.test(String(u));const f=window.fetch;window.fetch=async(...a)=>{const r=await f(...a);try{if(isAuth(typeof a[0]==='string'?a[0]:a[0].url))r.clone().json().then(show);}catch(e){}return r;};const o=XMLHttpRequest.prototype.open;XMLHttpRequest.prototype.open=function(m,u){if(isAuth(u))this.addEventListener('load',()=>{try{show(JSON.parse(this.responseText));}catch(e){}});return o.apply(this,arguments);};alert('Prêt : connectez-vous maintenant (sans recharger la page).');})()
```

1. Ouvrez https://mon-espace.ekwateur.fr/ ; déconnectez-vous si besoin pour arriver sur l'écran de connexion.
2. Lancez le favori (sur mobile : tapez « Jetons Ekwateur » dans la barre d'adresse et choisissez le favori). Un message « Prêt » s'affiche.
3. Connectez-vous normalement (e-mail, mot de passe, captcha).
4. Les jetons sont copiés (ou affichés pour copie). Collez-les dans Home Assistant.

Le favori ne fait que lire la réponse de connexion dans votre propre navigateur ; rien n'est envoyé ailleurs.

Sur ordinateur, vous pouvez aussi copier la réponse de la requête `POST /auth` dans F12 → Réseau.

**Sécurité** : le RefreshToken donne accès à votre compte pendant des semaines. Ne le partagez pas. En cas de fuite, changez votre mot de passe et déconnectez-vous ; selon la configuration d'Ekwateur, cela ne révoque pas forcément un RefreshToken déjà émis, qui reste alors valable jusqu'à son expiration.

## Endpoints utilisés (lecture seule)

- `GET /dashboard/user-information` : contrats
- `GET /v2/meters-readings/{ref}` : relèves
- `GET /v3/my_profile/bills_history/{ref}` : mensualités / factures
- `GET /billing/tariff-options/{ref}` : prix kWh + abonnement
- `POST /refresh_token` : renouvellement de session (le client Cognito a un secret, le renouvellement Cognito direct est impossible)

## Débogage

```yaml
logger:
  logs:
    custom_components.ekwateur: debug
```

Ne publiez jamais vos jetons dans une issue.

## Avertissement

Projet communautaire, non affilié à Ekwateur. Il utilise l'API non documentée de l'espace client, qui peut changer sans préavis.

## Licence

MIT
