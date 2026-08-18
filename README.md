![DTTSVG Banner](banenr.png)

# DTTSVG - Text To Speech Video Generator

DTTSVG est un **custom component Home Assistant** qui génère dynamiquement une vidéo d'onde sonore synchronisée avec n'importe quel moteur Text-To-Speech (TTS) configuré dans Home Assistant, puis la joue sur un écran connecté (comme le Google Nest Hub) via le protocole Cast.

Compatible avec **toutes les versions récentes de Home Assistant** et **tous les moteurs TTS** (Piper, Edge TTS, Google Translate, etc.) : le moteur est choisi dans l'interface de configuration.

---

## ✨ Fonctionnalités

- **Configuration 100% GUI** : Paramètres → Appareils & services → Ajouter une intégration → DTTSVG
  - Sélection du **moteur TTS** (liste dynamique de tous les moteurs configurés dans HA)
  - Sélection de la **langue** et de la **voix** selon le moteur
  - Sélection de l'**écran cible** (entité `media_player`, ex. Nest Hub)
  - Options : volume jour/nuit, coupure du son pendant la génération, couleur de l'onde, taille vidéo...
- **Entité `media_player.dttsvg_screen`** : écran virtuel dont l'état reflète l'écran réel ; toutes les commandes (play, pause, stop, volume) sont relayées à l'écran via Cast.
- **Service `dttsvg.speak`** : génère la vidéo depuis un texte et la joue sur l'écran.
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
   - Sélectionnez l'**écran cible** (votre `media_player.nest_hub` par exemple)
   - Personnalisez les options (volume jour/nuit, délai, couleur de l'onde, taille...)

Vous pouvez modifier tous ces réglages à tout moment via **Paramètres → Appareils & services → DTTSVG → Options**.

---

## 🎯 Utilisation

### Service `dttsvg.speak`

```yaml
action: dttsvg.speak
data:
  text: "Bonjour, je suis prêt !"
```

Champ optionnel `target` pour remplacer temporairement l'écran configuré :

```yaml
action: dttsvg.speak
data:
  text: "Message sur un autre écran"
  target: media_player.autre_ecran
```

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

---

## 🛠 Dépannage

- **"Aucun moteur TTS configuré"** : ajoutez une intégration TTS dans HA (Paramètres → Voix → Moteurs TTS) avant de configurer DTTSVG.
- **L'écran ne joue pas la vidéo** : vérifiez que le `media_player` cible est bien en ligne et que la vidéo est accessible (l'URL contient un jeton aléatoire, protégée en lecture seule).
- **Première installation lente** : Home Assistant installe automatiquement la dépendance PyAV (quelques dizaines de Mo).

---

## 📁 Structure

```
custom_components/dttsvg/
├── __init__.py        # Orchestration : TTS → vidéo → cast + service speak
├── manifest.json      # Métadonnées HACS / HA
├── config_flow.py     # Menu de configuration GUI
├── media_player.py    # Entité écran virtuelle
├── tts_compat.py      # Compatibilité multi-versions du composant TTS
├── video.py           # Génération vidéo (PyAV, H.264 + AAC)
├── view.py            # Endpoint de diffusion de la vidéo
├── translations/      # fr / en
└── images/            # Icône et logo HACS
```