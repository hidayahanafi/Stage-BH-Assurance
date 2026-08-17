"""
config.py
---------
Centralise les chemins de fichiers (au lieu de les avoir codés en dur dans
provisions.py, simulateur_final.py et app.py). Surchargeable par variables
d'environnement, pratique si le nom/emplacement des fichiers change (ex.
autre poste, autre serveur) sans toucher au code métier.
"""

import os

# Répertoire des données (par défaut : dossier courant du projet)
DATA_DIR = os.getenv("BH_DATA_DIR", os.path.dirname(os.path.abspath(__file__)))

FICHIER_CONTRATS = os.path.join(DATA_DIR, os.getenv("BH_FICHIER_CONTRATS", "prod_TDD.xlsx"))
FICHIER_MORTALITE = os.path.join(DATA_DIR, os.getenv("BH_FICHIER_MORTALITE", "TD 99.xlsx"))
FICHIER_PRIMES_SORTIE = os.path.join(DATA_DIR, "resultats_primes.xlsx")
FICHIER_PROVISIONS_SORTIE = os.path.join(DATA_DIR, "provisions_mathematiques.xlsx")

# Règles métier par défaut (reprises telles quelles de data_prep.py)
TAUX_INTERET_CREDIT = 0.07
TAUX_TECHNIQUE = 0.03
TAUX_CHARGEMENT_GESTION = 0.0002
TAUX_CHARGEMENT_ACQUISITION = 0.10
ABATTEMENT_MORTALITE = 0.40
