import pandas as pd
import numpy as np
from sklearn.experimental import enable_iterative_imputer  # noqa: F401 (active IterativeImputer)
from sklearn.impute import IterativeImputer
from sklearn.linear_model import BayesianRidge

import config


def charger_et_nettoyer_donnees(chemin_contrats: str, chemin_td99: str):
    """
    Importe, nettoie et prépare les bases de données pour le simulateur PM.
    Retourne (df_propres, dict_Lx, dict_dx1) ou (None, None, None) en cas d'échec.
    """
    print("Chargement des fichiers Excel en cours...")

    try:
        df_contrats = pd.read_excel(chemin_contrats)
        df_mortalite = pd.read_excel(chemin_td99)
    except FileNotFoundError as e:
        print(f"Erreur : Fichier introuvable. Vérifie tes chemins. Détails : {e}")
        return None, None, None

    # Nettoyage des noms de colonnes
    df_contrats.columns = df_contrats.columns.str.strip().str.lower()
    df_mortalite.columns = df_mortalite.columns.str.strip()

    # --- Transformation de la table TD99 en dictionnaires ---
    # On utilise Lx (survivants bruts) et dx1 (décès bruts), sans actualisation
    # intégrée. Dx et Cx sont déjà actualisés à 3% dans la table source ; les
    # combiner au taux propre de chaque contrat créerait une double actualisation.
    df_mortalite = df_mortalite.sort_values(by="Age")

    # --- Abattement de mortalité ---
    # La table TD99 est ancienne : on réduit la mortalité pour refléter la
    # réalité démographique actuelle du portefeuille.
    abattement = config.ABATTEMENT_MORTALITE
    df_mortalite["qx"] = df_mortalite["dx1"] / df_mortalite["Lx"]
    df_mortalite["qx_abattu"] = df_mortalite["qx"] * (1 - abattement)

    l_x_courant = 100000.0
    nouveaux_Lx, nouveaux_dx = [], []
    for qx_new in df_mortalite["qx_abattu"]:
        nouveaux_Lx.append(l_x_courant)
        dx_new = l_x_courant * qx_new
        nouveaux_dx.append(dx_new)
        l_x_courant -= dx_new

    df_mortalite["Lx"] = nouveaux_Lx
    df_mortalite["dx1"] = nouveaux_dx

    dict_Lx = df_mortalite.set_index("Age")["Lx"].to_dict()
    dict_dx1 = df_mortalite.set_index("Age")["dx1"].to_dict()

    # --- Typage des dates ---
    colonnes_dates = [
        "date_naissance", "effet_contrat", "date_entree_risque",
        "expiration", "date_sortie_risque",
    ]
    for col in colonnes_dates:
        if col in df_contrats.columns:
            df_contrats[col] = pd.to_datetime(df_contrats[col], errors="coerce")

    # --- Typage des variables numériques ---
    colonnes_numeriques = [
        "montant_credit_normal", "taux_interet_applique", "taux_technique",
        "duree_contrat", "duree_credit_normal", "duree_garantie", "quotite",
        "prime_nette",
    ]
    for col in colonnes_numeriques:
        if col in df_contrats.columns:
            df_contrats[col] = pd.to_numeric(df_contrats[col], errors="coerce")

    # Suppression des lignes inutilisables
    df_propres = df_contrats.dropna(
        subset=["date_naissance", "montant_credit_normal", "effet_contrat"]
    ).copy()

    # Âge à la souscription
    df_propres["Age_Souscription"] = (
        df_propres["effet_contrat"].dt.year - df_propres["date_naissance"].dt.year
    )

    # Filtrer les âges aberrants (erreurs de saisie -> âges négatifs/irréalistes)
    df_propres = df_propres[
        (df_propres["Age_Souscription"] >= 18) & (df_propres["Age_Souscription"] <= 85)
    ]

    print("Application des règles métier :")
    print(f"   - Taux d'intérêt du crédit : {config.TAUX_INTERET_CREDIT}")
    df_propres["taux_interet_applique"] = config.TAUX_INTERET_CREDIT

    print(f"   - Taux technique (Note TD99) : {config.TAUX_TECHNIQUE}")
    df_propres["taux_technique"] = config.TAUX_TECHNIQUE

    print(f"   - Chargement gestion : {config.TAUX_CHARGEMENT_GESTION}")
    df_propres["taux_chargement_gestion"] = config.TAUX_CHARGEMENT_GESTION

    print(f"   - Chargement acquisition : {config.TAUX_CHARGEMENT_ACQUISITION}")
    df_propres["taux_chargement_acquisition"] = config.TAUX_CHARGEMENT_ACQUISITION

    # Standardisation de la quotité (doit être entre 0 et 1)
    if "quotite" in df_propres.columns and len(df_propres) > 0:
        if df_propres["quotite"].max() > 1:
            df_propres["quotite"] = df_propres["quotite"] / 100.0

    print(f"Nettoyage terminé. Nombre de contrats exploitables : {len(df_propres)}")

    # --- Imputation des durées manquantes/invalides via MICE ---
    print("Traitement des durées via MICE (Iterative Imputer)...")

    df_propres["duree_temporaire"] = df_propres["duree_contrat"].fillna(
        df_propres["duree_credit_normal"]
    )
    df_propres.loc[df_propres["duree_temporaire"] <= 0, "duree_temporaire"] = np.nan

    features_imputation = ["Age_Souscription", "montant_credit_normal", "duree_temporaire"]
    df_features = df_propres[features_imputation]

    # BayesianRidge est le modèle par défaut de IterativeImputer, adapté ici
    # car il gère bien l'incertitude des prédictions.
    imputer = IterativeImputer(estimator=BayesianRidge(), max_iter=10, random_state=42)

    print("   -> Entraînement du modèle et prédiction des durées en cours...")
    df_imputed = pd.DataFrame(
        imputer.fit_transform(df_features),
        columns=features_imputation,
        index=df_propres.index,
    )

    df_propres["duree_contrat"] = df_imputed["duree_temporaire"].round().astype(int)

    nb_corriges = df_propres["duree_temporaire"].isna().sum()
    print(f"   -> {nb_corriges} contrats corrigés par imputation MICE.")

    df_propres = df_propres.drop(columns=["duree_temporaire"])

    return df_propres, dict_Lx, dict_dx1


def auditer_durees_invalides(df_portfolio: pd.DataFrame, export_path: str | None = None):
    """
    Isole et (optionnellement) exporte les contrats dont la durée est
    manquante ou <= 0 avant imputation — utile pour un rapport d'audit
    à destination de l'encadrant.
    """
    df_portfolio = df_portfolio.copy()
    df_portfolio["duree_mois_calculee"] = df_portfolio["duree_contrat"].fillna(
        df_portfolio["duree_credit_normal"]
    )

    contrats_invalides = df_portfolio[
        (df_portfolio["duree_mois_calculee"] <= 0) | (df_portfolio["duree_mois_calculee"].isnull())
    ].copy()

    colonnes_audit = [
        "num_contrat", "effet_contrat", "montant_credit_normal",
        "duree_contrat", "duree_credit_normal", "duree_mois_calculee",
    ]
    colonnes_existantes = [c for c in colonnes_audit if c in contrats_invalides.columns]
    rapport_anomalies = contrats_invalides[colonnes_existantes]

    nb_total = len(df_portfolio)
    nb_anomalies = len(rapport_anomalies)
    pourcentage = (nb_anomalies / nb_total * 100) if nb_total else 0.0

    print("\n--- DIAGNOSTIC DES DURÉES INVALIDES ---")
    print(f"Total des contrats analysés : {nb_total}")
    print(f"Contrats avec durée invalide (<= 0 ou vide) : {nb_anomalies}")
    print(f"Proportion : {pourcentage:.2f}% de la base\n")

    if nb_anomalies > 0 and export_path:
        rapport_anomalies.to_excel(export_path, index=False)
        print(f"Fichier '{export_path}' généré avec succès.")
    elif nb_anomalies == 0:
        print("Aucune durée invalide détectée dans la base.")

    return rapport_anomalies


if __name__ == "__main__":
    print("Démarrage du pipeline de préparation des données...")
    df_portfolio, dict_Lx, dict_dx1 = charger_et_nettoyer_donnees(
        config.FICHIER_CONTRATS, config.FICHIER_MORTALITE
    )

    if df_portfolio is not None:
        print("\nAperçu des contrats après correction du taux :")
        colonnes_a_afficher = ["date_naissance", "Age_Souscription", "montant_credit_normal", "taux_interet_applique"]
        if "num_contrat" in df_portfolio.columns:
            colonnes_a_afficher.insert(0, "num_contrat")
        print(df_portfolio[colonnes_a_afficher].head())

        print("\nLancement de l'audit des durées de contrats...")
        auditer_durees_invalides(df_portfolio, export_path="Audit_Anomalies_Durees.xlsx")
