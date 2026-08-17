import pandas as pd

import config
from actuariat import calcul_crd, calculer_primes
from data_prep import charger_et_nettoyer_donnees


def tarifer_portefeuille(df_propres: pd.DataFrame, dict_Lx: dict, dict_dx1: dict) -> pd.DataFrame:
    """
    Calcule les 3 primes (unique pure / inventaire / commerciale) pour
    chaque contrat du portefeuille.
    """
    primes_uniques, primes_inventaires, primes_commerciales = [], [], []

    for compteur, (_, row) in enumerate(df_propres.iterrows()):
        if compteur > 0 and compteur % 5000 == 0:
            print(f"   Traitement en cours... {compteur} contrats calculés.")

        age_x = int(row["Age_Souscription"])
        duree_mois = int(row["duree_contrat"])
        n_ans = (duree_mois // 12) + (1 if duree_mois % 12 != 0 else 0)

        if n_ans <= 0:
            primes_uniques.append(0.0)
            primes_inventaires.append(0.0)
            primes_commerciales.append(0.0)
            continue

        capital = row["montant_credit_normal"]
        taux_p = row["taux_interet_applique"]
        taux_tech = row["taux_technique"]
        g = row["taux_chargement_gestion"]
        alpha = row["taux_chargement_acquisition"]

        crd_mensuel = calcul_crd(capital, taux_p, n_ans * 12)
        resultat = calculer_primes(age_x, crd_mensuel, taux_tech, g, alpha, dict_Lx, dict_dx1)

        if resultat is None:
            primes_uniques.append(0.0)
            primes_inventaires.append(0.0)
            primes_commerciales.append(0.0)
        else:
            primes_uniques.append(resultat.prime_unique_pure)
            primes_inventaires.append(resultat.prime_inventaire)
            primes_commerciales.append(resultat.prime_commerciale)

    df_final = df_propres.copy()
    df_final["Prime_Unique_Pure_Calculee"] = primes_uniques
    df_final["Prime_Inventaire"] = primes_inventaires
    df_final["Prime_Commerciale"] = primes_commerciales

    colonnes_finales = [
        "num_contrat", "Age_Souscription", "montant_credit_normal",
        "duree_contrat", "Prime_Unique_Pure_Calculee", "Prime_Inventaire", "Prime_Commerciale",
    ]
    df_final = df_final[colonnes_finales].copy()
    df_final["num_contrat"] = df_final["num_contrat"].astype(str)
    df_final = df_final.sort_values(by="num_contrat", ascending=True)
    return df_final


if __name__ == "__main__":
    df_propres, dict_Lx, dict_dx1 = charger_et_nettoyer_donnees(
        config.FICHIER_CONTRATS, config.FICHIER_MORTALITE
    )

    if df_propres is None:
        raise ValueError("Arrêt du simulateur : impossible de charger les données.")

    df_final = tarifer_portefeuille(df_propres, dict_Lx, dict_dx1)

    print("\n=== RÉSULTATS DE LA TARIFICATION (Aperçu) ===")
    print(df_final.head(10).to_string(index=False))

    df_final.to_excel(config.FICHIER_PRIMES_SORTIE, index=False)
    print(f"\nRésultats exportés dans : {config.FICHIER_PRIMES_SORTIE}")
