import pandas as pd
import numpy as np
from data_prep import charger_et_nettoyer_donnees


def calcul_capital_restant_du(capital_initial, taux_pret_annuel, duree_mois):
    """Génère le tableau d'amortissement."""
    if taux_pret_annuel <= 0:  
        return [capital_initial - (capital_initial / duree_mois) * m for m in range(1, duree_mois + 1)]

    taux_mensuel = taux_pret_annuel / 12
    echeance = (capital_initial * taux_mensuel) / (1 - (1 + taux_mensuel) ** (-duree_mois))

    crd = []
    capital_courant = capital_initial
    for mois in range(1, duree_mois + 1):
        crd.append(capital_courant)
        interet = capital_courant * taux_mensuel
        principal = echeance - interet
        capital_courant -= principal
    return crd


fichier_contrats = 'prod_TDD.xlsx'
fichier_mortalite = 'TD 99.xlsx'

df_propres, dict_Lx, dict_dx1 = charger_et_nettoyer_donnees(fichier_contrats, fichier_mortalite)

if df_propres is None:
    raise ValueError(" Arrêt du simulateur : Impossible de charger les données.")


echantillon = df_propres.copy()


primes_uniques = []
primes_inventaires = []
primes_commerciales = []

for compteur, (idx, row) in enumerate(echantillon.iterrows()):

    if compteur > 0 and compteur % 5000 == 0:
        print(f"   Traitement en cours... {compteur} contrats calculés.")

    num_contrat = row["num_contrat"]
    age_x = int(row["Age_Souscription"])

    duree_mois = int(row["duree_contrat"]) 
    n_ans = (duree_mois // 12) + (1 if duree_mois % 12 != 0 else 0)
    
    capital = row["montant_credit_normal"]
    taux_p = row["taux_interet_applique"]

    if n_ans <= 0:
        primes_uniques.append(0)
        primes_inventaires.append(0)
        primes_commerciales.append(0)
        continue

    crd_mensuel = calcul_capital_restant_du(capital, taux_p, n_ans * 12)

    pu_pret = 0
    pi_pret = 0
    pc_pret = 0

    Lx_souscription = dict_Lx.get(age_x, 0)   

    taux_tech = row["taux_technique"] 
    g         = row["taux_chargement_gestion"]
    alpha     = row["taux_chargement_acquisition"]

    duree_mois_crd = len(crd_mensuel)

    if Lx_souscription > 0:
        denominateur_comm = Lx_souscription * (1 - alpha)
        
        for k in range(1, duree_mois_crd + 1):
            t = (k - 1) // 12
            age_atteint = age_x + t

            dx1_t  = dict_dx1.get(age_atteint, 0)   
            Lx_t   = dict_Lx.get(age_atteint, 0)    

            dx1_prime_t = dx1_t + (g * Lx_t)

            S_k = crd_mensuel[k - 1]
            facteur_actu = (1 + taux_tech) ** (-k / 12)

            facteur_commun = (S_k * (1 / 12) * facteur_actu) / Lx_souscription
            facteur_commer = (S_k * (1 / 12) * facteur_actu) / denominateur_comm

            pu_pret += dx1_t       * facteur_commun   
            pi_pret += dx1_prime_t * facteur_commun   
            pc_pret += dx1_prime_t * facteur_commer   

    primes_uniques.append(round(pu_pret, 3))
    primes_inventaires.append(round(pi_pret, 3))
    primes_commerciales.append(round(pc_pret, 3))

echantillon["Prime_Unique_Pure_Calculee"] = primes_uniques
echantillon["Prime_Inventaire"] = primes_inventaires
echantillon["Prime_Commerciale"] = primes_commerciales

colonnes_finales = [
    'num_contrat', 'Age_Souscription', 'montant_credit_normal',
    'duree_contrat', 'Prime_Unique_Pure_Calculee', 'Prime_Inventaire', 'Prime_Commerciale'
]

df_final = echantillon[colonnes_finales].copy()

df_final = df_final.sort_values(by='num_contrat', ascending=True)


df_final['num_contrat'] = df_final['num_contrat'].astype(str)

print("\n=== RÉSULTATS DE LA TARIFICATION (Aperçu) ===")
print(df_final.head(10).to_string(index=False))

fichier_sortie = "resultats_primes.xlsx"
df_final.to_excel(fichier_sortie, index=False)

print(f"\n Résultats exportés dans : {fichier_sortie}")