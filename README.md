# DTTSVG — Domus Text-To-Speech Video Generator

<p align="center">
  <img src="images/banner.png" alt="DTTSVG Banner" width="100%">
</p>

<p align="center">
  <a href="https://github.com/hacs/default"><img src="https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge" alt="HACS Custom"></a>
  <a href="https://github.com/ilyasselyaouti/DTTSVG/releases"><img src="https://img.shields.io/github/v/release/ilyasselyaouti/DTTSVG?style=for-the-badge&color=blue" alt="Release"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge" alt="License MIT"></a>
  <a href="https://www.buymeacoffee.com/ilyassinc"><img src="https://img.shields.io/badge/Buy_Me_A_Coffee-FFDD00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black" alt="Buy Me A Coffee"></a>
  <a href="https://github.com/sponsors/ilyasselyaouti"><img src="https://img.shields.io/badge/Sponsor-GitHub-ea4aaa?style=for-the-badge&logo=github" alt="GitHub Sponsors"></a>
</p>

**DTTSVG** (Domus Text-To-Speech Video Generator) est un composant personnalisé pour **Home Assistant**. Il génère dynamiquement une vidéo d'onde sonore synchronisée avec vos moteurs TTS (Piper, Edge TTS, Google Translate...) et la diffuse sur vos écrans connectés (Google Nest Hub, Cast) via le protocole Google Cast.

---

## 📸 Démonstration

> *(Un GIF/Vidéo de démonstration sera ajouté très prochainement.)*

---

## ✨ Fonctionnalités actuelles

- **Configuration 100% GUI** : Assistant de configuration fluide dans l'interface Home Assistant.
- **Moteur vidéo embarqué (PyAV)** : Génération H.264 + AAC sans nécessiter FFmpeg sur le système hôte.
- **Support Multi-Moteurs TTS** : Détection automatique des moteurs TTS configurés sur votre instance.
- **Gestion des priorités & File d'attente** :
  - **Annonces prioritaires** : Diffusion immédiate sur l'écran cible.
  - **Annonces standards** : Mises en file d'attente (jusqu'à 10 annonces) si l'enceinte/écran est occupé.
- **Écran de secours (Fallback)** : Redirection automatique vers un second écran ou enceinte si l'appareil principal est hors ligne.
- **Entité dédiée `media_player.dttsvg_screen`** : Reflète l'état de l'écran cible et permet de relancer la dernière vidéo ou d'envoyer du texte directement.

---

## 📋 Prérequis

- **Home Assistant** : Version 2023.5 ou supérieure.
- **Moteur TTS** : Au moins un moteur TTS actif dans votre installation (`Piper`, `Edge TTS`, `Google Translate`, etc.).
- **Appareil Cast** : Un écran compatible Google Cast (ex: Nest Hub) ou un lecteur média configuré.

---

## 🚀 Installation

### Via HACS (Dépôt Personnalisé)

Étant donné que le dépôt est public et compatible HACS, vous pouvez l'ajouter directement comme dépôt personnalisé :

1. Dans Home Assistant, ouvrez **HACS** $\rightarrow$ **Intégrations**.
2. Cliquez sur les **trois petits points** en haut à droite $\rightarrow$ **Dépôts personnalisés** (*Custom repositories*).
3. Saisissez l'URL : `https://github.com/ilyasselyaouti/DTTSVG`
4. Sélectionnez la catégorie **Intégration** (*Integration*), puis cliquez sur **Ajouter**.
5. Recherchez **DTTSVG** dans la liste HACS, puis cliquez sur **Télécharger**.
6. Redémarrez Home Assistant.

### Installation Manuelle

1. Téléchargez ce dépôt.
2. Copiez-le dans le répertoire `custom_components/` de votre dossier de configuration Home Assistant (`/config/custom_components/dttsvg/`).
3. Redémarrez Home Assistant.

---

## ⚙️ Configuration

1. Allez dans **Paramètres** $\rightarrow$ **Appareils & services** $\rightarrow$ **Ajouter une intégration**.
2. Recherchez **DTTSVG**.
3. Choisissez le moteur TTS, la voix, l'écran cible et optionnellement l'écran de secours.

Vous pouvez ajuster les options à tout moment via **Paramètres** $\rightarrow$ **Appareils & services** $\rightarrow$ **DTTSVG** $\rightarrow$ **Options**.

---

## 🎯 Utilisation

### Action `dttsvg.speak`

Vous pouvez lancer des annonces via le service/action `dttsvg.speak` :

```yaml
action: dttsvg.speak
data:
  text: "Bonjour ! La vidéo d'onde sonore est générée en temps réel."

```

#### Exemple avec paramètres avancés :

```yaml
action: dttsvg.speak
data:
  text: "Attention, présence détectée dans le jardin."
  target: media_player.nest_hub_salon
  priority: true

```

---

## 🗺️ Roadmap & Fonctionnalités à venir

* [ ] Intégration de démonstrations visuelles (GIFs / Vidéos courtes).
* [ ] Stabilisation et test complet du *Smart Ducking* (baisse du volume du média en cours pendant l'annonce).
* [ ] Application mobile Android dédiée pour recevoir les annonces en overlay flottant style Gemini Live.
* [ ] Soumission du dépôt à la liste officielle par défaut de HACS.

---

## 💖 Soutenir le projet

Si vous appréciez DTTSVG et souhaitez soutenir son développement :

<a href="https://www.buymeacoffee.com/ilyassinc"><img src="https://img.shields.io/badge/Buy_Me_A_Coffee-FFDD00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black" alt="Buy Me A Coffee"></a>
  <a href="https://github.com/sponsors/ilyasselyaouti"><img src="https://img.shields.io/badge/Sponsor-GitHub-ea4aaa?style=for-the-badge&logo=github" alt="GitHub Sponsors"></a>

---

## 📜 Licence

Ce projet est distribué sous licence **MIT**. Voir le fichier [LICENSE](https://www.google.com/search?q=LICENSE&utm_source=gemini) pour plus de précisions.


### Résumé des ajustements effectués :

1. **Overlay Android retiré** : Déplacé dans la section **Roadmap** pour indiquer clairement que c'est une fonctionnalité en développement.
2. **Smart Ducking précisé** : Placé dans la Roadmap pour test et stabilisation sans fausses promesses dans les fonctionnalités actuelles.
3. **Explication HACS ajustée** : Explication claire de la procédure "Dépôt personnalisé" (*Custom repository*).
4. **Section Démo / GIF** : Message propre indiquant l'arrivée prochaine du GIF de démo.