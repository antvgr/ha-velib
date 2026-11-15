# Reprise — capture de la requête batterie via émulateur Android

Le redémarrage pour le BIOS ferme la session Claude. Ce fichier dit où on en est et quoi faire.

## Où on en est
- L'intégration **stations publiques** fonctionne (testée). Le **compte** (connexion, trajets) fonctionne aussi via `login_check_client`.
- **Batterie / note par vélo** : le format est connu (`docs/API.md`), mais le serveur ne renvoie le tableau `bikes[]` qu'à l'appli mobile authentique. iPhone impossible (certificate pinning). → on capture via **émulateur Android** + HTTP Toolkit (contourne le pinning avec Frida).
- APK officiel déjà extrait : `%LOCALAPPDATA%\velib-tools\apk\xapk\com.paris.velib.apk`.
- HTTP Toolkit installé. Android Studio en cours d'installation.

## Étape 1 — Activer la virtualisation (toi, maintenant)
1. Redémarre et entre dans le **BIOS/UEFI** (touche au démarrage : souvent `Suppr`, `F2`, `F10` selon la carte mère).
2. Active **Intel VT-x** (« Intel Virtualization Technology ») ou, si CPU AMD, **SVM Mode / AMD-V**.
3. Enregistre et quitte (souvent `F10`).
4. De retour sous Windows : *Activer ou désactiver des fonctionnalités Windows* → coche **Plateforme de l'hyperviseur Windows** → redémarre.

Vérif rapide (PowerShell) : `Get-CimInstance Win32_Processor | select VirtualizationFirmwareEnabled` doit être `True`.

## Étape 2 — Reprendre avec Claude (nouvelle session)
Rouvre ce projet dans Claude Code et dis : « reprends la capture émulateur ». Claude fera :
1. Vérifier Android Studio + créer un émulateur **Google APIs** (image *rootable*, pas « Play Store »), API 34, x86_64.
2. Lancer l'émulateur, y installer `com.paris.velib.apk` (`adb install`).
3. Dans **HTTP Toolkit** : interception **Android device via ADB** (installe le certificat système + bypass pinning Frida).
4. Toi : ouvrir l'appli Vélib' dans l'émulateur, te connecter, ouvrir une **station avec vélos électriques** puis le détail d'un vélo.
5. Claude : repérer la requête `/api/map/details` (ou autre) dont la réponse contient `bikes` avec `bikeBatteryLevel` → relever l'URL exacte, les en-têtes d'auth, les paramètres.
6. Claude : rejouer la requête, puis brancher les capteurs batterie/note dans l'intégration.

## Rappels
- Identifiants Vélib' : saisis par toi dans l'appli (Claude ne les tape pas).
- Clé appli déchiffrée (bcrypt, = gate d'infra, ne débloque PAS la batterie) : `secrets.local.json`, hors git.
- Détails techniques complets : `docs/API.md`.
