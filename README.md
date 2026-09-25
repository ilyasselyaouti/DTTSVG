![DTTSVG Banner](banner.png)

# DTTSVG - Text To Speech Video Generator

DTTSVG est un **custom component Home Assistant** qui génère dynamiquement une vidéo d'onde sonore synchronisée avec n'importe quel moteur Text-To-Speech (TTS) configuré dans Home Assistant, puis la joue sur un écran connecté (comme le Google Nest Hub) via le protocole Cast.

Compatible avec **toutes les versions récentes de Home Assistant** et **tous les moteurs TTS** (Piper, Edge TTS, Google Translate, etc.) : le moteur est choisi dans l'interface de configuration.

---

## ✨ Fonctionnalités

- **Configuration 100% GUI** : Paramètres → Appareils & services → Ajouter une intégration → DTTSVG
  - Sélection du **moteur TTS** (liste dynamique de tous les moteurs configurés dans HA)
  - Sélection de la **langue** et de la **voix** selon le moteur
  - Sélection de l'**écran cible** (entité `media_player`, ex. Nest Hub) et de l'**écran/enceinte de backup** (optionnel)
  - Options : volume jour/nuit, coupure du son pendant la génération, couleur de l'onde, taille vidéo, **priorité par défaut**, **volume de ducking**, **routage téléphone**...
- **Entité `media_player.dttsvg_screen`** : écran virtuel dont l'état reflète l'écran réel ; toutes les commandes (play, pause, stop, volume) sont relayées à l'écran via Cast.
- **Service `dttsvg.speak`** : génère la vidéo depuis un texte et la joue sur l'écran.
- **Annonces prioritaires** : jouées immédiatement, avec **baisse automatique (ducking)** du volume du média en cours (si un écran de backup est configuré) puis **restauration** — le média n'est jamais coupé.
- **Annonces non prioritaires** : mises en **file d'attente** jusqu'à ce que l'enceinte soit libre.
- **Écran de backup** : utilisé automatiquement quand l'écran principal est hors ligne.
- **App mobile Android (overlay façon Gemini Live)** : si vous êtes actif sur votre téléphone, l'annonce s'affiche en overlay flottant sur le téléphone (dans vos écouteurs) au lieu des enceintes de la maison.
- **Encodage embarqué (PyAV)** : aucun FFmpeg système requis.
- Vidéos stockées dans `/media/dttsvg/` (visibles dans le navigateur média).

---

## 📋 Prérequis

- Home Assistant **2023.5 ou supérieur** (Container, Core, HAOS...)
- Au moins un moteur TTS configuré dans Home Assistant (ex : `Piper`, `Edge TTS`)

---

## 🚀 Installation

### Via HACS (recommandé)

1. Dans HACS → intégrations → menu (⋮) → **Dépôts personnalisés**
2. Ajoutez `https://github.com/ilyasselyaouti/DTTSVG` avec la catégorie **Intégration**
3. Recherchez **DTTSVG** dans HACS et installez-le
4. Redémarrez Home Assistant

### Manuellement

Copiez le dossier `custom_components/dttsvg/` dans le dossier `custom_components/` de votre installation Home Assistant, puis redémarrez.

---

## ⚙️ Configuration

1. Dans Home Assistant, allez dans **Paramètres → Appareils & services → Ajouter une intégration**
2. Recherchez **DTTSVG**
3. Suivez l'assistant :
   - Choisissez le **moteur TTS** à utiliser
   - Choisissez la **langue** et la **voix**
   - Sélectionnez l'**écran cible** (votre `media_player.nest_hub` par exemple) et éventuellement l'**écran/enceinte de backup**
   - Personnalisez les options (volume jour/nuit, délai, couleur de l'onde, taille, priorité, ducking, routage téléphone...)

Vous pouvez modifier tous ces réglages à tout moment via **Paramètres → Appareils & services → DTTSVG → Options**.

### Options spécifiques

| Option | Rôle |
|---|---|
| `Écran / enceinte de backup` | Fallback quand l'écran principal est hors ligne, et hôte des annonces prioritaires quand un média joue (le volume du média est alors baissé puis restauré) |
| `Annonces prioritaires par défaut` | Si activé, toutes les annonces sont prioritaires (sauf override par le service) |
| `Volume du média en cours pendant une annonce prioritaire` | Niveau de volume appliqué au média pendant l'annonce (ducking, ex. 0.15), restauré automatiquement ensuite |
| `Annoncer sur le téléphone s'il est actif` | Si activé (par défaut), les annonces sont envoyées à l'overlay de l'app mobile quand le téléphone est actif, au lieu des enceintes |

---

## 🎯 Utilisation

### Service `dttsvg.speak`

```yaml
action: dttsvg.speak
data:
  text: "Bonjour, je suis prêt !"
```

Champs optionnels :

- `target` : remplace temporairement l'écran configuré.
- `priority` : si `true`, l'annonce est jouée **immédiatement** (le volume du média en cours est baissé puis restauré si un backup existe) ; sinon elle est mise en **file d'attente** jusqu'à ce que l'enceinte soit libre. Par défaut, la valeur de l'option « Annonces prioritaires par défaut ».

```yaml
action: dttsvg.speak
data:
  text: "Message sur un autre écran"
  target: media_player.autre_ecran
```

```yaml
action: dttsvg.speak
data:
  text: "La sonnette a été activée"
  priority: true
```

### Logique de routage

1. **Téléphone actif** (app installée + écran allumé) → l'annonce part en overlay sur le téléphone, rien n'est joué sur les enceintes.
2. **Écran principal disponible et libre** → lecture normale.
3. **Écran principal hors ligne** → lecture sur l'écran/enceinte de backup (sinon file d'attente).
4. **Un média joue** :
   - annonce **prioritaire** → jouée sur le backup (ou l'écran principal si pas de backup) et le volume du média en cours est baissé (ducking) puis **restauré automatiquement** à la fin de l'annonce ;
   - annonce **non prioritaire** → mise en **file d'attente** (max. 10, les prioritaires passent devant) et jouée dès que l'enceinte est libre.

### Exemple de script

```yaml
alias: DTTSVG | Speak
icon: mdi:video-waveform
fields:
  texte_message:
    description: Texte à envoyer
    required: true
    selector:
      text: null
sequence:
  - action: dttsvg.speak
    data:
      text: "{{ texte_message }}"
```

### Entité media player

L'entité `media_player.dttsvg_screen` reflète l'état de l'écran réel (lecture, pause, volume...) et vous permet de :
- relancer la dernière vidéo générée depuis l'interface (carte media player),
- envoyer du texte directement depuis une carte média : `media_content_type: text` et `media_content_id: "votre texte"`.

### Événement

À chaque génération, l'événement `dttsvg_video_generated` est déclenché avec les attributs `text`, `url` et `path` (utile pour des automatisations).

Quand l'annonce est routée vers le téléphone, l'événement `dttsvg_phone_announcement` est aussi déclenché (mêmes attributs) — c'est celui que l'app mobile écoute.

---

## 📱 App mobile Android (overlay façon Gemini Live)

L'application Android affiche les annonces en **overlay flottant** au-dessus de toutes les applications (comme l'interface Gemini Live), avec la vidéo d'onde sonore qui joue et le texte de l'annonce.

### Principe

- L'app se connecte à Home Assistant (WebSocket) et écoute les événements `dttsvg_phone_announcement`.
- Elle signale en continu si le **téléphone est actif** (écran allumé) via un heartbeat vers l'intégration.
- Si le téléphone est actif au moment d'un `dttsvg.speak`, l'annonce est jouée **uniquement** sur le téléphone (dans vos écouteurs si vous en portez) — jamais sur les enceintes de la maison.

### Compilation

Prérequis : **Android Studio** (ou JDK 17 + Android SDK).

1. Ouvrez le dossier `android/` dans Android Studio.
2. Laissez Gradle synchroniser le projet (télécharge les dépendances). Si le wrapper Gradle est incomplet (`gradle-wrapper.jar` absent), Android Studio propose de le régénérer automatiquement — ou lancez `gradle wrapper` depuis `android/`.
3. *Build → Build Bundle(s) / APK(s) → Build APK(s)*.

L'APK se trouve dans `android/app/build/outputs/apk/debug/`.

### Installation et configuration

1. Installez l'APK sur votre téléphone (Android 8+).
2. Ouvrez l'app : renseignez l'**URL de Home Assistant** (`internal_url` ou `external_url` — elle doit être joignable depuis le téléphone) et un **jeton longue durée** (Profil → Jeton longue durée → Créer un jeton).
3. **Tester la connexion**, puis **Autoriser l'overlay** (Réglages → Applications → DTTSVG → Afficher par-dessus les autres applications).
4. Activez le service d'annonces. Une notification permanente « DTTSVG actif » apparaît.
5. Dans la config de l'intégration, vérifiez que **« Annoncer sur le téléphone s'il est actif »** est coché.

> **Note** : si l'URL de Home Assistant est en HTTPS avec un certificat auto-signé, le téléphone doit l'accepter (import du certificat, ou `external_url` valide).

---

## 🛠 Dépannage

- **"Aucun moteur TTS configuré"** : ajoutez une intégration TTS dans HA (Paramètres → Voix → Moteurs TTS) avant de configurer DTTSVG.
- **L'écran ne joue pas la vidéo** : vérifiez que le `media_player` cible est bien en ligne et que la vidéo est accessible (l'URL contient un jeton aléatoire, protégée en lecture seule).
- **L'annonce n'arrive pas sur le téléphone** : vérifiez que l'app est active (notification « DTTSVG actif »), que l'URL et le jeton sont corrects (test de connexion), que la permission overlay est accordée et que l'écran du téléphone est allumé.
- **Le volume du média n'est pas restauré après une annonce prioritaire** : la restauration dépend de la détection de fin de lecture sur l'écran (état `playing` → `idle`). Si le média ne remonte jamais l'état, la restauration intervient au bout de 10 s (sécurité).
- **Première installation lente** : Home Assistant installe automatiquement la dépendance PyAV (quelques dizaines de Mo).

---

## 📁 Structure

```
custom_components/dttsvg/
├── __init__.py        # Orchestration : TTS → vidéo → cast + service speak + routage/queue/ducking
├── manifest.json      # Métadonnées HACS / HA
├── config_flow.py     # Menu de configuration GUI
├── media_player.py    # Entité écran virtuelle
├── phone.py           # Endpoint heartbeat de l'app mobile
├── tts_compat.py      # Compatibilité multi-versions du composant TTS
├── video.py           # Génération vidéo (PyAV, H.264 + AAC)
├── view.py            # Endpoint de diffusion de la vidéo
├── translations/      # fr / en
└── images/            # Icône et logo HACS

android/               # App mobile Android (Kotlin, overlay façon Gemini Live)
└── app/src/main/java/com/dttsvg/app/
    ├── MainActivity.kt        # Réglages (URL HA, jeton, permissions)
    ├── HaClient.kt            # WebSocket HA + heartbeat d'activité
    ├── OverlayService.kt      # Service foreground
    ├── AnnouncementOverlay.kt # Overlay flottant + lecture vidéo (ExoPlayer)
    ├── PhoneActiveTracker.kt  # Détection écran allumé
    ├── NotificationHelper.kt  # Notifications (fallback + service)
    └── Prefs.kt               # Préférences
```