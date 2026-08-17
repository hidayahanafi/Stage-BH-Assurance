# StageBH - Assurance ADE

Projet d'actuariat pour la tarification et l'analyse des provisions d'assurance emprunteur ADE.

> ⚠️ **Confidentialité** : ce dépôt ne contient aucune donnée client réelle.
> Les fichiers `.xlsx` (portefeuille, table de mortalité, résultats) sont
> exclus via `.gitignore` et ne doivent jamais être commités. Pour faire
> tourner le projet, fournis tes propres fichiers de données au même format
> de colonnes (voir `data_prep.py`).

## Fonctionnalités

- Préparation et nettoyage des données contrat / mortalité (avec imputation
  MICE des durées de contrat manquantes).
- Calcul des primes uniques, primes d'inventaire et primes commerciales.
- Simulation d'un contrat avec évolution de la provision mathématique.
- Tableau de bord Streamlit pour rechercher un contrat existant et lancer
  une nouvelle simulation.
- Analyse de mortalité par tranches d'âge sur la base des données
  portefeuille et de la table TD 99.

## Structure du projet

- `actuariat.py` : logique de calcul actuariel partagée (amortissement,
  primes, provisions) — vectorisée avec numpy.
- `config.py` : chemins de fichiers et paramètres métier (taux, abattement)
  centralisés.
- `app.py` : interface Streamlit.
- `data_prep.py` : préparation, nettoyage et imputation des données.
- `simulateur_final.py` : calcul batch des primes et export vers Excel.
- `provisions.py` : calcul batch des provisions mathématiques et export
  vers Excel.
- `AnalyseMortalite99.Rmd` / `visualisation_actuarielle.Rmd` : supports de
  restitution et d'analyse (visualisations anonymisées).
- Fichiers Excel générés (non versionnés) : `resultats_primes.xlsx`,
  `provisions_mathematiques.xlsx`, `Analyse_Mortalite_Tranches_Tardifs.xlsx`.

## Prérequis

- Python 3.10 ou plus récent.
- Les fichiers de données suivants dans le dossier du projet (non fournis
  dans ce dépôt) :
  - `prod_TDD.xlsx`
  - `TD 99.xlsx`

## Installation

Créer et activer un environnement virtuel, puis installer les dépendances :

```
python3 -m venv env
source env/bin/activate   # Windows : env\Scripts\activate
pip install -r requirements.txt
```

## Lancement

### Calcul des primes

```
python simulateur_final.py
```

### Calcul des provisions

```
python provisions.py
```

### Tableau de bord Streamlit

```
streamlit run app.py
```

## Remarques

- Le dépôt ignore les environnements locaux (`env/`), les caches Python et
  les fichiers de données/résultats générés.
- Les résultats sont exportés au format Excel dans le dossier du projet
  (en local uniquement, jamais versionnés).
