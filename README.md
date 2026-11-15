# Vélib' Métropole pour Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)

Intégration non officielle pour les Vélib' à Paris et en Métropole.

* **Stations (données publiques, sans compte)** : vélos disponibles (mécaniques / électriques), bornes libres, capacité, état de la station, et **batterie + note de chaque vélo électrique**.
* **Compte Vélib' (optionnel)** : dernier trajet (date, distance, durée, vitesse, stations, vélo électrique ou non), nombre de trajets, distance totale, CO₂ économisé, minutes bonus. Un événement `velib_new_trip` est émis à chaque nouveau trajet.

> ⚠️ La partie compte utilise l'API privée du site velib-metropole.fr, non documentée. Elle peut cesser de fonctionner sans préavis, et son usage automatisé n'est probablement pas prévu par les CGU. Les données sont interrogées toutes les 15 minutes.
>
> Sur certains réseaux, velib-metropole.fr peut renvoyer une erreur 403 (Cloudflare) aux requêtes du client HTTP de Home Assistant. Si la configuration du compte échoue avec « cannot_connect » alors que vos identifiants sont bons, c'est probablement ce blocage, propre à l'IP/au réseau de votre instance.

### Niveau de batterie et note des vélos électriques

**Inclus**, et **sans compte** ! Pour chaque station suivie, l'intégration ajoute :

* **Meilleure batterie vélo élec** (`%`) : meilleur niveau parmi les vélos électriques dispos.
* **Vélos élec bien chargés** : nombre de vélos électriques avec batterie ≥ 2/3.
* Le capteur **Vélos électriques** expose en attributs le détail par vélo : numéro, niveau de batterie (0–3 et ~%), note (1–3 étoiles), en charge, statut.

Données issues de `POST /api/secured/searchStation` (voir [docs/API.md](docs/API.md)). La batterie est un niveau **grossier sur 3** (comme les barres de l'appli), converti en ~% pour l'affichage.

## Installation

### HACS (dépôt personnalisé)

1. HACS → ⋮ → *Dépôts personnalisés* → URL de ce dépôt, catégorie *Intégration*.
2. Installer **Vélib' Métropole**, redémarrer Home Assistant.

### Manuelle

Copier `custom_components/velib` dans le dossier `custom_components` de votre configuration, puis redémarrer.

## Configuration

*Paramètres → Appareils et services → Ajouter une intégration → Vélib' Métropole*, puis choisir :

* **Suivre des stations** : recherche par nom ou numéro (vide = stations les plus proches du domicile défini dans HA). Une entrée unique ; ajoutez ou retirez des stations via *Configurer*.
* **Connecter mon compte** : identifiant et mot de passe de velib-metropole.fr. Plusieurs comptes possibles.

## Entités

| Appareil | Entités |
|---|---|
| Station | Vélos disponibles, Vélos mécaniques, Vélos électriques, Bornes libres, Capacité, Dernière remontée, Location possible, Retour possible |
| Compte | Dernier trajet (+ attributs), Distance / Durée / Vitesse moyenne du dernier trajet, Nombre de trajets, Distance totale, CO₂ économisé, Minutes bonus |

### Exemple d'automatisation

```yaml
triggers:
  - trigger: event
    event_type: velib_new_trip
actions:
  - action: notify.mobile_app_mon_telephone
    data:
      message: >
        Trajet de {{ (trigger.event.data.distance_m / 1000) | round(1) }} km
        de {{ trigger.event.data.departure_station }} à {{ trigger.event.data.arrival_station }}.
```

## Développement

`scripts/probe_account.py` teste l'API sans Home Assistant (identifiants dans `.env`, ignoré par git) :

```text
VELIB_USERNAME=...
VELIB_PASSWORD=...
```

En cas de souci avec le compte, joignez le **téléchargement des diagnostics** de l'entrée (données personnelles masquées) à votre ticket.
