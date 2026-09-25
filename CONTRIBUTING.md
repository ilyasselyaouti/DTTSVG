# Guide de contribution à DTTSVG

Merci de ton intérêt pour le projet **DTTSVG** ! Les contributions de la communauté (corrections de bugs, améliorations de code, ajouts de documentation) sont les bienvenues pour faire évoluer le composant.

---

## 📋 Sommaire

1. [Règles de bonne conduite](#-règles-de-bonne-conduite)
2. [Signaler un bug](#-signaler-un-bug)
3. [Proposer une fonctionnalité](#-proposer-une-fonctionnalité)
4. [Mettre en place l'environnement de développement](#-mettre-en-place-lenvironnement-de-développement)
5. [Soumettre une Pull Request (PR)](#-soumettre-une-pull-request-pr)

---

## 🤝 Règles de bonne conduite

En participant à ce projet, tu t'engages à :
- Rester respectueux et constructif dans les échanges (Issues, Discussions, PR).
- Fournir des retours précis et étayés en cas de problème.

---

## 🐛 Signaler un bug

Avant d'ouvrir un ticket, vérifie dans la liste des [Issues](https://github.com/ilyasselyaouti/DTTSVG/issues) que le problème n'a pas déjà été signalé.

Si le bug est nouveau, ouvre une Issue avec le modèle suivant :
- **Titre clair** : Décris le problème en quelques mots.
- **Contexte** :
  - Version de Home Assistant (ex: `2026.8.0`)
  - Type d'installation (HAOS, Docker, Core)
  - Version de DTTSVG
  - Moteur TTS utilisé (Piper, Edge TTS, etc.) et appareil cible (ex: Google Nest Hub)
- **Étapes pour reproduire** : Indique la séquence exacte qui déclenche le bug.
- **Comportement attendu vs comportement observé**.
- **Logs** : Extrait des journaux Home Assistant (`Settings` -> `System` -> `Logs`).

---

## 💡 Proposer une fonctionnalité

Les propositions d'amélioration sont fortement encouragées !

1. Consulte la section **Roadmap** du `README.md` pour vérifier que la fonctionnalité n'est pas déjà planifiée.
2. Ouvre une **Issue** de type *Feature Request* pour exposer ton besoin et discuter de l'implémentation avant de développer du code.

---

## 🛠️ Mettre en place l'environnement de développement

 DTTSVG est un composant personnalisé pour Home Assistant écrit en Python et utilisant la bibliothèque PyAV pour la génération vidéo.

1. **Fork** le dépôt sur ton compte GitHub.
2. **Clone** ton fork localement :
   ```bash
   git clone [https://github.com/VOTRE_PSEUDO/DTTSVG.git](https://github.com/VOTRE_PSEUDO/DTTSVG.git)
   cd DTTSVG

```

3. **Lier le composant à une instance de test Home Assistant** :
Copie ou crée un lien symbolique (*symlink*) du dossier `custom_components/dttsvg` vers le répertoire `custom_components/` de ton instance HA de développement :
```bash
ln -s /chemin/vers/DTTSVG/custom_components/dttsvg /chemin/vers/ha_config/custom_components/dttsvg

```


4. Redémarre Home Assistant pour charger tes modifications.

---

## 🚀 Soumettre une Pull Request (PR)

1. Crée une branche dédiée depuis la branche `main` :
```bash
git checkout -b feature/nom-de-ta-fonctionnalite
# ou
git checkout -b fix/nom-du-bug

```


2. Fais tes modifications et teste-les rigoureusement sur Home Assistant.
3. Rédige des messages de commit clairs et explicites.
4. Pousse ta branche sur ton fork :
```bash
git push origin feature/nom-de-ta-fonctionnalite

```


5. Ouvre une **Pull Request** vers la branche `main` du dépôt original en décrivant clairement :
* Les modifications apportées.
* Les tests effectués.
* L'Issue associée s'il y en a une (ex: `Closes #12`).