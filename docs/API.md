# API Vélib' Métropole — notes de rétro-ingénierie

État au 15/11/2026. Rien de tout ceci n'est documenté officiellement (sauf le GBFS) : ça peut changer sans préavis.

## 1. Open data GBFS (public, sans authentification)

Base : `https://velib-metropole-opendata.smovengo.cloud/opendata/Velib_Metropole/`

| Fichier | Contenu |
|---|---|
| `gbfs.json` | index des flux |
| `system_information.json` | infos système |
| `station_information.json` | `station_id`, `stationCode`, `name`, `lat`, `lon`, `capacity` |
| `station_status.json` | `num_bikes_available`, `num_bikes_available_types: [{"mechanical": n}, {"ebike": n}]`, `num_docks_available`, `is_installed`, `is_renting`, `is_returning`, `last_reported` (epoch s) |

Clé de jointure : `stationCode` (chaîne, ex. `"16107"`). Rafraîchi ~1/min.

## 2. API du site www.velib-metropole.fr

> ⚠️ **Cloudflare (15/11/2026)** : tout le domaine renvoie `403` aux requêtes faites avec `aiohttp` (le client HTTP de Home Assistant), alors que `curl` et `urllib` passent depuis la même machine. La partie compte de l'intégration est donc **non vérifiée et probablement bloquée** en l'état.

### Publique

`GET /api/map/details?listeCodeStation=16107[,…]` — sans authentification. Exemple :

```json
[{"station":{"gps":{"latitude":48.86,"longitude":2.27},"stationType":"PUBLIC","state":"Operative",
  "name":"…","code":"16107","type":"yes","dueDate":1531632033,"openingHours":null},
  "nbBike":0,"nbEbike":0,"nbFreeDock":0,"nbFreeEDock":34,"creditCard":"no","nbDock":0,"nbEDock":35,
  "nbBikeOverflow":0,"nbEBikeOverflow":0,"kioskState":"yes","overflow":"no","overflowActivation":"no",
  "maxBikeOverflow":0,"densityLevel":1,"nbBikeBlockedToCollect":0,"nbBikeBlockedToFixInStation":1,"isAltitude":0}]
```

Variante : `?listeIdStation=<id>,<id>`. Infos en plus du GBFS : état (`state`), overflow, vélos bloqués. **Pas de détail par vélo ni de batterie.**

### Authentification (formulaire Symfony, session par cookie)

1. `GET /fr/login` → HTML contenant `<input type="hidden" name="_csrf_token" value="…">` + cookie `SULUSESSID`.
2. `POST /login` (form-urlencoded), sans suivre la redirection :
   `_username`, `_password`, `_csrf_token`, `_remember_me=on`, `numFailures=0`, `redirectAfterLogin=`, `localeUrlParams=fr`
   * échec → `302 Location: /login?error=error.login`
   * succès → `302` vers une autre page ; les cookies de session authentifient ensuite `/api/private/*`.
3. Session expirée → les endpoints privés répondent `401 {"code":0,"message":"Unauthorized"}` → refaire 1-2.

Pas de captcha observé. `POST /api/secured/login_check_client` (JSON) existe mais est bloqué par Cloudflare (403) hors navigateur ; il n'est utilisé par le site qu'après un changement de mot de passe.

### Endpoints privés (cookie de session)

| Endpoint | Utilisation |
|---|---|
| `GET /api/private/getAllInfosUser` | `{generalDetails, card, subscriptions, …}` |
| `GET /api/private/getCurrentUser` | ≈ `generalDetails` |
| `GET /api/private/getCourseList?limit=10&offset=0` | trajets (sans `limit` : tous) |
| `GET /api/private/listFavoriteStation`, `listFavoriteStationCode` | favoris |
| `GET /api/private/subscription`, `getPayments`, `getUnpaidInvoices` | abonnement, paiements |

Autres trouvés dans le bundle (non utilisés, certains en écriture — ne pas appeler) : `addFavoriteStation`, `deleteFavoriteStation`, `changePassword`, `profile/updateUser`, `resetAccessId`, `getPaymentCardList`, `getOfferUpgrade`, `getPaymentDoc`, `getSubscriptionDoc`, `getUnpaidInvoiceDoc`, `/api/secured/searchStation` (POST).

#### `generalDetails` (champs lus par le site)

* `customerIndicators.distanceGlobalCounter` (m), `globalSavedCarbonDioxide` (g), `tripCounter`, `tripAverageDuration`, `tripHighestDistance`, `totalTraveled`, `longestTrip`, `trophies`
* `customerBonusDetails.currentYear` (minutes bonus)
* `customerDetails.{name, address, contactDetails}`, `login`

#### `getCourseList`

```text
{ paging: { totalNumberOfRecords },
  walletOperations: [ {
    operationDate,            // date du trajet
    parameter1: "yes"|"no",   // vélo électrique ?
    quantity,                 // durée en secondes
    amountWithTax, currency,  // coût éventuel
    parameter3: { BIKEID, DISTANCE (m), AVERAGE_SPEED (km/h), SAVED_CARBON_DIOXIDE,
                  departureStationId, arrivalStationId, BONUS_EARNED, USED_BONUS }
  } ] }
```

Les types exacts (format de `operationDate`, code ou id de station) sont à confirmer sur une vraie réponse : `scripts/probe_account.py --raw` ou les diagnostics HA.

## 3. Batterie et note des vélos — via l'appli mobile (APK 8.9.0, `com.paris.velib`)

Rétro-ingénierie statique de l'APK officiel (jadx). L'appli (Kotlin, Retrofit + Moshi) utilise **le même hôte** `https://www.velib-metropole.fr` (`BuildConfig.BASE_URL`).

### Endpoint : le MÊME que la carte, mais authentifié

```
GET /api/map/details?listeCodeStation=16107[,40001,…]
GET /api/map/details?gpsTopLatitude=..&gpsTopLongitude=..&gpsBotLatitude=..&gpsBotLongitude=..&zoomLevel=..
```

Réponse : `List<StationDto>`. **Quand la requête est authentifiée**, chaque station contient en plus un tableau `bikes` (absent de l'appel public anonyme) :

```jsonc
[{
  "station": { "code": "16107", "name": "…", "gps": {…}, "state": "Operative" },
  "nbBike": 3, "nbEbike": 2, "nbFreeDock": 20, "nbDock": 0, "creditCard": "no",
  "overflow": "no", "maxBikeOverflow": 0,
  "bikes": [
    {
      "dockPosition": "12",        // n° de borne ("" ou 4 chiffres = overflow)
      "bikeName": "16302",         // n° du vélo
      "bikeElectric": "yes",       // "yes" | "no"
      "bikeStatus": "…",           // état (maintenance…)
      "charging": true,            // en charge
      "bikeBatteryLevel": "2_SUR_3", // voir table ci-dessous
      "bikeRate": "2",             // note: "1" | "2" | "3" (sinon non noté)
      "lastRateDate": "2026-11-10T08:00:00Z"
    }
  ]
}]
```

**Batterie** (`bikeBatteryLevel`) — niveau grossier sur 3, comme les barres de l'appli (pas un pourcentage) :

| Valeur | Sens | Enum appli |
|---|---|---|
| `0_SUR_3` | vide | EMPTY |
| `1_SUR_3` | faible | LOW |
| `2_SUR_3` | moyen | MEDIUM |
| `3_SUR_3` | plein | HIGH |
| (autre / absent) | inconnu | UNKNOWN |

**Note** (`bikeRate`) : `"1"`/`"2"`/`"3"` = 1 à 3 étoiles ; absent = non noté. Noter un vélo (après un trajet) : `POST /api/private/bikeRate`.

### ✅ La batterie/note : `POST /api/secured/searchStation` (public, sans compte)

**C'est le bon endpoint** (confirmé par capture de l'appli puis rejeu en Python, 15/11/2026). `/api/map/details` ne renvoie jamais `bikes[]` ; `searchStation` si.

```
POST https://www.velib-metropole.fr/api/secured/searchStation
Headers:
  Authorization: Bearer null          ← l'appli l'envoie telle quelle quand non connectée ; accepté
  Content-Type: application/json; charset=UTF-8
  Accept: application/json
  User-Agent: okhttp/5.x              (un UA de navigateur marche aussi)
Body:
  {"disponibility": "yes", "stationName": "<nom ou sous-chaîne>"}
```

* `disponibility: "yes"` est **la clé** qui fait inclure le tableau `bikes[]` (avec `""` : pas de `bikes`).
* `stationName` est un **filtre par sous-chaîne** du nom. `""` renvoie **toutes** les stations (1522, ~5 Mo, dont ~1445 avec vélos). Par nom : 1 station, ~1 Ko.
* **Aucune authentification réelle requise** : `Bearer null` suffit. Pas besoin du compte utilisateur ni de la clé appli (`moba:$2y$…`, qui est un simple gate d'infra).
* Réponse : `List<StationDto>`, chaque station avec `bikes[]` :

```jsonc
{ "station": {"code":"15027","name":"Duhamel - André Gide","gps":{…}, "state":"Operative"},
  "nbBike":0, "nbEbike":2, "nbFreeEDock":17, …,
  "bikes": [
    { "bikeName":"87794", "bikeElectric":"yes", "bikeBatteryLevel":"2_SUR_3",
      "bikeRate":3, "numberOfRates":7, "charging":false, "bikeStatus":"disponible",
      "dockPosition":"11", "lastRateDate":"2026-11-14T14:02:43Z", "stationId":6497 } ] }
```

Table batterie : `0_SUR_3`→0 (vide), `1_SUR_3`→1, `2_SUR_3`→2, `3_SUR_3`→3 (plein). `bikeRate` : entier 1–3 (0/absent = non noté). Vélos mécaniques : pas de batterie.

> ⚠️ Cloudflare : velib-metropole.fr renvoie 403 à certains clients HTTP selon l'IP/l'empreinte (aiohttp a été bloqué sur le PC de dev, urllib passait). L'intégration tente aiohttp puis bascule sur le client standard Python.

---

### (historique) Authentification de `/api/map/details` — déclencheur de `bikes[]` NON reproduit

La clé statique de l'appli (`core/network/security/DecryptionKt` + `ValueDecrypter`, AES-GCM-128) a été **déchiffrée** (clé `com.batch.android.o0.h`, IV et jeton dans `core/network/BuildConfig`). Résultat : `user = "moba"`, `token = "$2y$..."` — un **hash bcrypt**, c'est-à-dire un identifiant de **gate Basic d'infrastructure (htpasswd / reverse-proxy)**, pas l'auth de l'API. Il sert aussi au `BasicAuthWebViewClient` (auth HTTP de WebView).

Tests réels (urllib, 15/11/2026) sur `/api/map/details?listeCodeStation=9020,40001` — **aucun ne renvoie le champ `bikes`** :

| Essai | `bikes[]` |
|---|---|
| anonyme | absent |
| `Authorization: Bearer <jeton compte user>` | absent |
| `Authorization: Basic <clé appli déchiffrée>` | absent |
| Basic + `User-Agent: okhttp/4.12.0` + en-têtes mobiles | absent |
| requête station unique | absent |

**Conclusion :** le serveur ne renvoie `bikes[]` (batterie + note) qu'à l'appli mobile authentique, via un mécanisme non déductible de l'APK seul (probable attestation d'intégrité / session mobile, ou en-tête signé). Le seul moyen fiable de trouver la requête exacte est de **capturer une vraie requête de l'appli** (HTTP Toolkit, déjà installé) depuis un émulateur (virtualisation BIOS requise) ou le téléphone via ADB, puis de la rejouer.

Ce qui FONCTIONNE sans capture : données publiques par station (GBFS + `/api/map/details` compteurs) et, avec le compte de l'utilisateur, `login_check_client` → `getCourseList` (trajets) / `getAllInfosUser` (stats).

### Autres endpoints de l'appli (host `www.velib-metropole.fr`)

* `GET /api/map/details?listeIdStation=<id>,…` → `List<LocatedStationDto>`
* `POST /api/secured/searchStation`, `GET /api/secured/offers/{language}`, `/api/secured/register`, `/api/secured/login_check_client`
* privés (en-tête `Authorization: Bearer <jeton>` via `UserAuthenticationInterceptor`) : `getCurrentUser`, `getCourseList`, `getPaymentList`, `getUnpaidInvoices`, `addFavoriteStation`, `bikeRate`, `ingenico/*`, `uploadImage`…
* Prévisions de disponibilité : autre hôte `https://api.qucit.com/bikepredict/v3/` (intercepteur dédié).
