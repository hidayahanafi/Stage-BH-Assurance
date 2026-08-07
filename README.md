# StageBH - Assurance ADE

Projet d'actuariat pour la tarification et l'analyse des provisions d'assurance emprunteur ADE.

## Fonctionnalités

- Préparation et nettoyage des données contrat / mortalité.
- Calcul des primes uniques, primes d'inventaire et primes commerciales.
- Simulation d'un contrat avec évolution de la provision mathématique.
- Tableau de bord Streamlit pour rechercher un contrat existant et lancer une nouvelle simulation.
- Analyse de mortalité par tranches d'âge sur la base des données portefeuille et de la table TD 99.

## Structure du projet

- `app.py` : interface Streamlit.
- `data_prep.py` : préparation, nettoyage et imputation des données.
- `simulateur_final.py` : calcul batch des primes et export vers Excel.
- `provisions.py` : calcul batch des provisions mathématiques et export vers Excel.
- `AnalyseMortalite99.Rmd` / `visualisation_actuarielle.Rmd` : supports de restitution et d'analyse.
- Fichiers Excel générés : `resultats_primes.xlsx`, `provisions_mathematiques.xlsx`, `Analyse_Mortalite_Tranches_Tardifs.xlsx`.

## Prérequis

- Python 3.10 ou plus récent.
- Les fichiers de données suivants dans le dossier du projet :
  - `prod_TDD.xlsx`
  - `TD 99.xlsx`

## Installation

Créer et activer un environnement virtuel, puis installer les dépendances :

```bash
pip install -r requirements.txt
```

## Lancement

### Tableau de bord Streamlit

```bash
streamlit run app.py
```

### Calcul des primes

```bash
python simulateur_final.py
```

### Calcul des provisions

```bash
python provisions.py
```

## Remarques

- Le dépôt ignore maintenant les environnements locaux, les caches Python et les fichiers générés lourds.
- Les résultats sont exportés au format Excel dans le dossier du projet.