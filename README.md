# 🖱️⌨️ Activity Tracker & Dashboard

> **Outil local de suivi d'activité PC** — capture souris + clavier, dashboard web interactif, 100 % local, aucune donnée envoyée sur Internet.

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-Active-brightgreen)

---

## ⚠️ Avertissement confidentialité

Ce projet capture **en continu** tes clics souris, tes frappes clavier, les mots que tu tapes et les applications que tu utilises.

- ✅ **Tout reste local** : aucune requête réseau sortante, aucune télémétrie.
- ✅ Les données sont stockées dans deux fichiers JSON à la racine du projet.
- 🔴 **Ne partage JAMAIS `mouse_data.json` ni `keyboard_data.json`** — ils contiennent l'historique complet de ton activité (mots de passe potentiellement inclus si tapés hors champs masqués).
- ✅ Ces fichiers sont déjà listés dans le `.gitignore`.
- 🎯 Usage strictement personnel recommandé.

---

## ✨ Features

### 🖱️ Tracking souris
- Distance totale parcourue (px → mètres → kilomètres)
- Clics gauche / droit / molette + détection **double-clic**
- Détection **drag & drop** avec distance et durée
- Scroll (up / down / distance équivalente en pixels)
- Intervalle moyen entre clics
- **Heatmap multi-écrans** (un canvas par moniteur, séparé par bouton)
- Carte des drags avec flèches directionnelles

### ⌨️ Tracking clavier
- Compteur total de frappes + catégorisation (lettres, chiffres, espaces, modificateurs, navigation, symboles, fonctions…)
- Compteur de **mots tapés** avec détection intelligente (buffer + backspace + navigation)
- **WPM en direct** (moyenne glissante 1h)
- **Top mots** avec **stemming bilingue FR/EN** (via NLTK SnowballStemmer) → regroupe les variantes (`travailler`, `travaille`, `travaillé` → 1 seul stem)
- Filtrage automatique des **stopwords** FR + EN (200+ mots exclus)
- Détection des **raccourcis clavier** : Ctrl+C, Ctrl+V, Ctrl+Z, Alt+Tab, Win+D… (25+ combos reconnus)
- Top 24 touches les plus utilisées

### 📊 Dashboard web
Ouvre `http://localhost:5000` — 5 onglets :

| Onglet | Contenu |
|---|---|
| 🖱️ **Souris** | KPI clics, heatmaps, drag map, distance avec **comparaisons fun** (Tour Eiffel, girafe, pizza Sénior, Christ Rédempteur, Titanic, Boeing 747…) |
| ⌨️ **Clavier** | KPI frappes, WPM, top touches, top mots, raccourcis, vocabulaire distinct |
| 📈 **Analyse** | Carte calendrier type GitHub (52 semaines), score productivité, corrélation souris/clavier par heure, détection d'**anomalies** (z-score), comparaison "toi vs toi" |
| 🪟 **Applications** | Répartition clics + frappes par application active (Chrome, VSCode, Excel…) |
| 🏆 **Records** | Meilleur jour clics/frappes/drags/scroll, mot le plus tapé, streak jours consécutifs, distance parcourue vs 300+ objets de référence (du CD au diamètre du Soleil ☀️) |

### 🎨 Extras
- 🪟 **Suivi par application** (Windows) : quelle app utilises-tu le plus ?
- ⏸️ **Détection des pauses** : périodes d'inactivité > 5 min automatiquement loggées
- 📅 **Filtres temporels** partout : aujourd'hui, hier, 7j, 30j, semaine, mois, année, 12 mois, tout, **période libre**, **mode comparaison**
- 🚀 **Autostart Windows** (via registre `HKCU\Run`)
- 🍔 **Icône dans la system tray** (via pystray)
- 🎯 **Widget flottant** always-on-top (via tkinter)
- 🖥️ **Détection multi-écrans dynamique** (rebranchement à chaud toutes les 5s)

---

## 🛠️ Stack technique

- **Backend** : Python 3.10+ (`pynput`, `http.server`, `threading`)
- **Frontend** : HTML / CSS / JS vanilla + **Chart.js 4.4** (via CDN)
- **NLP** : NLTK Snowball Stemmer (FR + EN)
- **UI système** : `pystray` + `Pillow` (tray), `tkinter` (widget), `ctypes` (Windows API)
- **Persistance** : deux fichiers JSON (aucune BDD)

---

## 📦 Installation

```bash
# 1. Cloner le repo
git clone https://github.com/GuillaumeBlais/activity-tracker.git
cd activity-tracker

# 2. (Recommandé) Créer un environnement virtuel
python -m venv .venv
# Windows :
.venv\Scripts\activate
# Linux/macOS :
source .venv/bin/activate

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. (Optionnel) Télécharger les données NLTK pour le stemming
python -c "import nltk; nltk.download('punkt')"
```

---

## ▶️ Lancement

```bash
python tracker.py
```

Puis ouvre ton navigateur sur **http://localhost:5000**.

Le tracker :
1. Détecte automatiquement tes écrans
2. Démarre les hooks souris + clavier (nécessite parfois des droits admin sur Windows)
3. Lance un serveur HTTP local sur le port 5000
4. Sauvegarde toutes les 10 secondes dans les fichiers JSON

Pour l'arrêter : `Ctrl+C` dans le terminal ou clic droit sur l'icône tray → *Quitter*.

---

## 📁 Structure du projet

```
activity-tracker/
├── tracker.py            # Backend : capture + serveur HTTP
├── dashboard.html        # Frontend : dashboard 5 onglets
├── mouse_data.json       # 🔒 Données souris (généré, gitignoré)
├── keyboard_data.json    # 🔒 Données clavier (généré, gitignoré)
├── requirements.txt      # Dépendances Python
├── .gitignore
└── README.md
```

---

## 🔒 Vie privée

- 🚫 **Aucune requête réseau sortante** — vérifie avec Wireshark si tu veux.
- 🏠 Le serveur HTTP écoute uniquement sur `127.0.0.1` (localhost).
- 🗄️ Les données restent sur ta machine, dans ton dossier projet.
- 🙈 Les `.json` sont ignorés par git — tu ne les commiteras pas par accident.
- ⚠️ Reste tout de même prudent : ces fichiers contiennent une **quantité considérable d'informations personnelles**. Chiffre ton disque, ne les partage pas.

---

## 📝 License

MIT © Guillaume Blais

---

## 🤝 Contributions

Projet perso à l'origine — mais les PR sont bienvenues (nouvelles références de distance, améliorations dashboard, support Linux/macOS pour le suivi d'application, etc.).

---

*Made with ☕ et beaucoup de clics.*
