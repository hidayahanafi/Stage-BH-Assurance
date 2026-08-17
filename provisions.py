import time

import pandas as pd

import config
from actuariat import calcul_crd, calculer_prime_inventaire_seule
from data_prep import charger_et_nettoyer_donnees


def calculer_provisions_portefeuille(df_propres: pd.DataFrame, dict_Lx: dict, dict_dx1: dict) -> pd.DataFrame:
    """
    Calcule la trajectoire de provision mathématique année par année pour
    chaque contrat du portefeuille.
    """
    print(f"\nDémarrage du calcul des provisions sur {len(df_propres)} contrats...")
    debut_chrono = time.time()

    resultats = []
    for compteur, (_, row) in enumerate(df_propres.iterrows()):
        if compteur > 0 and compteur % 5000 == 0:
            print(f"   Traitement en cours... {compteur} contrats provisionnés.")

        num_contrat = row["num_contrat"]
        age_x = int(row["Age_Souscription"])
        capital = row["montant_credit_normal"]
        taux_p = row["taux_interet_applique"]

        duree_mois_total = int(row["duree_contrat"])
        n_ans = (duree_mois_total // 12) + (1 if duree_mois_total % 12 != 0 else 0)
        if n_ans <= 0:
            continue

        taux_tech = row["taux_technique"]
        g = row["taux_chargement_gestion"]

        crd_complet = calcul_crd(capital, taux_p, n_ans * 12)

        for t in range(n_ans + 1):
            mois_ecoule = t * 12
            age_atteint = age_x + t
            duree_restante_ans = n_ans - t

            if duree_restante_ans <= 0:
                provision_t = 0.0
            else:
                crd_restant = crd_complet[mois_ecoule: mois_ecoule + duree_restante_ans * 12]
                provision_t = calculer_prime_inventaire_seule(
                    age_atteint, crd_restant, taux_tech, g, dict_Lx, dict_dx1
                )

            crd_t = crd_complet[mois_ecoule] if mois_ecoule < len(crd_complet) else 0.0
            resultats.append({
                "num_contrat": num_contrat,
                "Age_Souscription": age_x,
                "Capital_Initial": capital,
                "Duree_Totale_Ans": n_ans,
                "t": t,
                "Age_Atteint": age_atteint,
                "Duree_Restante_Ans": duree_restante_ans,
                "CRD_au_mois_t": round(float(crd_t), 2),
                "Provision_t": provision_t,
            })

    print(f"Calcul terminé en {time.time() - debut_chrono:.1f}s")
    return pd.DataFrame(resultats)


if __name__ == "__main__":
    df_propres, dict_Lx, dict_dx1 = charger_et_nettoyer_donnees(
        config.FICHIER_CONTRATS, config.FICHIER_MORTALITE
    )

    if df_propres is None:
        raise ValueError("Arrêt du simulateur : impossible de charger les données.")

    df_provisions = calculer_provisions_portefeuille(df_propres, dict_Lx, dict_dx1)

    print("\n=== APERÇU DES PROVISIONS (10 premières lignes) ===")
    print(df_provisions.head(10).to_string(index=False))

    df_provisions.to_excel(config.FICHIER_PROVISIONS_SORTIE, index=False)
    print(f"\nProvisions exportées dans : {config.FICHIER_PROVISIONS_SORTIE}")
