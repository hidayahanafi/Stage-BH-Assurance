import pandas as pd
import numpy as np
import time
from data_prep import charger_et_nettoyer_donnees


def calcul_capital_restant_du(capital_initial, taux_pret_annuel, duree_mois):
    """Génère le tableau d'amortissement complet (liste des CRD mensuels)."""
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


def calcul_prime_inventaire(age_x, crd_mensuel, taux_tech, g, dict_Lx, dict_dx1):
    """
    Calcule la Prime Unique Inventaire.
    Toute l'actualisation financière est portée par `facteur_actu`, appliqué
    mois par mois. Les mortalités Lx/dx1 ne doivent donc PAS être ré-actualisées
    en plus via v^age : ce serait une double actualisation (déjà repérée mais
    pas corrigée dans la version précédente de ce fichier, où v^age_atteint et
    v^(age_atteint+1) étaient appliqués en plus de facteur_actu).
    """
    v = 1 / (1 + taux_tech)

    Lx_base = dict_Lx.get(age_x, 0)

    if Lx_base <= 0:
        return 0.0

    duree_mois = len(crd_mensuel)
    pi = 0.0

    for k in range(1, duree_mois + 1):
        annee = (k - 1) // 12
        age_atteint = age_x + annee

        # Mortalité brute, non actualisée (l'actualisation se fait uniquement
        # via facteur_actu ci-dessous)
        Lx_atteint = dict_Lx.get(age_atteint, 0)
        dx_atteint = dict_dx1.get(age_atteint, 0)

        # Application du chargement de gestion
        dx_prime_t   = dx_atteint + (g * Lx_atteint)
        S_k          = crd_mensuel[k - 1]
        facteur_actu = (1 + taux_tech) ** (-k / 12)

        pi += dx_prime_t * (S_k / 12) * facteur_actu / Lx_base

    return round(pi, 3)


fichier_contrats = 'prod_TDD.xlsx'
fichier_mortalite = 'TD 99.xlsx'

df_propres, dict_Lx, dict_dx1 = charger_et_nettoyer_donnees(fichier_contrats, fichier_mortalite)

if df_propres is None:
    raise ValueError(" Arrêt du simulateur : Impossible de charger les données.")

echantillon = df_propres.copy()

print(f"\n Démarrage du calcul des provisions sur {len(echantillon)} contrats (Base MICE)...")
debut_chrono = time.time()

# Création d'une liste pour stocker les lignes du futur DataFrame de provisions
resultats = []   

for compteur, (idx, row) in enumerate(echantillon.iterrows()):

    # Affichage adapté aux gros volumes pour ne pas saturer le terminal
    if compteur > 0 and compteur % 5000 == 0:
        print(f"   Traitement en cours... {compteur} contrats provisionnés.")

    num_contrat = row["num_contrat"]
    age_x       = int(row["Age_Souscription"])
    capital     = row["montant_credit_normal"]
    taux_p      = row["taux_interet_applique"]

    # Plus besoin de gestion de fallback, data_prep garantit des durées propres
    duree_mois_total = int(row["duree_contrat"])
    n_ans = (duree_mois_total // 12) + (1 if duree_mois_total % 12 != 0 else 0)

    if n_ans <= 0:
        continue

    # Récupération des taux standardisés
    taux_tech = row["taux_technique"]            
    g         = row["taux_chargement_gestion"]   

    # Tableau d'amortissement complet (tous les mois du contrat)
    crd_complet = calcul_capital_restant_du(capital, taux_p, n_ans * 12)

    for t in range(n_ans + 1):

        mois_ecoule  = t * 12                    
        age_atteint  = age_x + t                 
        duree_restante_ans  = n_ans - t          

        # Provision nulle en fin de contrat
        if duree_restante_ans <= 0:
            provision_t = 0.0
        else:
            # Sous-tableau du CRD pour la durée restante
            crd_restant = crd_complet[mois_ecoule : mois_ecoule + duree_restante_ans * 12]

            provision_t = calcul_prime_inventaire(
                age_x       = age_atteint,
                crd_mensuel = crd_restant,
                taux_tech   = taux_tech,
                g           = g,
                dict_Lx     = dict_Lx,
                dict_dx1    = dict_dx1
            )

        resultats.append({
            "num_contrat"       : num_contrat,
            "Age_Souscription"  : age_x,
            "Capital_Initial"   : capital,
            "Duree_Totale_Ans"  : n_ans,
            "t"                 : t,
            "Age_Atteint"       : age_atteint,
            "Duree_Restante_Ans": duree_restante_ans,
            "CRD_au_mois_t"     : round(crd_complet[mois_ecoule], 2) if mois_ecoule < len(crd_complet) else 0,
            "Provision_t"       : provision_t
        })


df_provisions = pd.DataFrame(resultats)

print("\n=== APERÇU DES PROVISIONS (10 premières lignes) ===")
print(df_provisions.head(10).to_string(index=False))

fichier_sortie = "provisions_mathematiques.xlsx"
df_provisions.to_excel(fichier_sortie, index=False)
print(f"\n Provisions exportées dans : {fichier_sortie}")