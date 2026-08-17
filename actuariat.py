"""
actuariat.py
------------
Module partagé pour le moteur de tarification et de provisionnement
(contrats de prévoyance adossés à des crédits bancaires).

Toute la logique de calcul qui était dupliquée dans app.py, provisions.py
et simulateur_final.py vit maintenant ici, à un seul endroit :
- calcul_crd()            : tableau d'amortissement (capital restant dû)
- calculer_primes()       : primes unique pure / inventaire / commerciale
                             pour UN contrat (version vectorisée numpy)
- calculer_provision_t()  : provision mathématique à l'instant t

Les 3 primes utilisent le même principe d'équivalence actuarielle :
  - Prime Unique Pure (pu)        : sans chargement
  - Prime d'Inventaire (pi)       : + chargement de gestion (g)
  - Prime Commerciale (pc)        : + chargement d'acquisition (alpha)

Actualisation : toute l'actualisation financière est portée par le
facteur_actu = (1 + taux_tech) ** (-k/12), appliqué mois par mois.
Les Lx / dx1 issus de la table de mortalité sont utilisés BRUTS
(non réactualisés), pour éviter une double actualisation.
"""

from dataclasses import dataclass
import numpy as np


def calcul_crd(capital: float, taux_annuel: float, duree_mois: int) -> np.ndarray:
    """
    Génère le tableau d'amortissement (capital restant dû, un point par mois).

    Si taux_annuel <= 0, amortissement linéaire (cas dégénéré, ex. tests).
    Sinon, amortissement classique à échéance constante.
    """
    if duree_mois <= 0:
        return np.array([])

    if taux_annuel <= 0:
        m = np.arange(1, duree_mois + 1)
        return capital - (capital / duree_mois) * m

    taux_mensuel = taux_annuel / 12
    echeance = (capital * taux_mensuel) / (1 - (1 + taux_mensuel) ** (-duree_mois))

    crd = np.empty(duree_mois)
    capital_courant = capital
    for m in range(duree_mois):
        crd[m] = capital_courant
        interet = capital_courant * taux_mensuel
        principal = echeance - interet
        capital_courant -= principal
    return crd


@dataclass
class ResultatTarification:
    prime_unique_pure: float
    prime_inventaire: float
    prime_commerciale: float


def _vecteurs_mortalite(age_x: int, duree_mois: int, dict_Lx: dict, dict_dx1: dict):
    """
    Construit, pour chaque mois k du contrat, les vecteurs numpy
    Lx(age atteint) et dx1(age atteint) — évite de refaire les dict.get()
    dans une boucle Python mois par mois.
    """
    k = np.arange(1, duree_mois + 1)
    annees = (k - 1) // 12
    ages_atteints = age_x + annees

    Lx_arr = np.array([dict_Lx.get(a, 0.0) for a in ages_atteints])
    dx1_arr = np.array([dict_dx1.get(a, 0.0) for a in ages_atteints])
    return k, Lx_arr, dx1_arr


def calculer_primes(
    age_x: int,
    crd_mensuel: np.ndarray,
    taux_tech: float,
    g: float,
    alpha: float,
    dict_Lx: dict,
    dict_dx1: dict,
) -> ResultatTarification | None:
    """
    Calcule les 3 primes pour un contrat, en vectorisant la boucle mensuelle
    (remplace la boucle Python `for k in range(1, duree_mois+1): ...` par
    des opérations numpy vectorisées — gain net sur un portefeuille de
    plusieurs milliers de contrats).
    """
    Lx_souscription = dict_Lx.get(age_x, 0.0)
    if Lx_souscription <= 0 or len(crd_mensuel) == 0:
        return None

    duree_mois = len(crd_mensuel)
    k, Lx_t, dx1_t = _vecteurs_mortalite(age_x, duree_mois, dict_Lx, dict_dx1)

    dx1_prime_t = dx1_t + (g * Lx_t)
    facteur_actu = (1 + taux_tech) ** (-k / 12)

    denominateur_comm = Lx_souscription * (1 - alpha)
    facteur_commun = (crd_mensuel * (1 / 12) * facteur_actu) / Lx_souscription
    facteur_commer = (crd_mensuel * (1 / 12) * facteur_actu) / denominateur_comm

    pu = float(np.sum(dx1_t * facteur_commun))
    pi = float(np.sum(dx1_prime_t * facteur_commun))
    pc = float(np.sum(dx1_prime_t * facteur_commer))

    return ResultatTarification(round(pu, 3), round(pi, 3), round(pc, 3))


def calculer_prime_inventaire_seule(
    age_x: int,
    crd_mensuel: np.ndarray,
    taux_tech: float,
    g: float,
    dict_Lx: dict,
    dict_dx1: dict,
) -> float:
    """
    Version allégée de calculer_primes() qui ne renvoie que la prime
    d'inventaire — utilisée par le calcul des provisions mathématiques
    (provisions.py), où seule pi est nécessaire à chaque instant t.
    """
    Lx_base = dict_Lx.get(age_x, 0.0)
    if Lx_base <= 0 or len(crd_mensuel) == 0:
        return 0.0

    duree_mois = len(crd_mensuel)
    k, Lx_t, dx1_t = _vecteurs_mortalite(age_x, duree_mois, dict_Lx, dict_dx1)

    dx1_prime_t = dx1_t + (g * Lx_t)
    facteur_actu = (1 + taux_tech) ** (-k / 12)

    pi = np.sum(dx1_prime_t * (crd_mensuel / 12) * facteur_actu / Lx_base)
    return round(float(pi), 3)


def simuler_contrat_complet(
    age_x: int,
    capital: float,
    duree_mois: int,
    taux_p: float,
    taux_tech: float,
    g: float,
    alpha: float,
    dict_Lx: dict,
    dict_dx1: dict,
):
    """
    Simule un contrat de bout en bout : primes + trajectoire des provisions
    mathématiques année par année. Utilisée par l'app Streamlit (simulation
    interactive) et peut aussi servir de base à un futur calcul batch.

    Retourne (primes: ResultatTarification, df_provisions compatible pandas)
    """
    crd_mensuel = calcul_crd(capital, taux_p, duree_mois)
    primes = calculer_primes(age_x, crd_mensuel, taux_tech, g, alpha, dict_Lx, dict_dx1)
    if primes is None:
        return None, []

    n_ans = (duree_mois // 12) + (1 if duree_mois % 12 != 0 else 0)
    lignes_provisions = []

    for t in range(n_ans + 1):
        mois_ecoule = t * 12
        age_atteint = age_x + t
        duree_restante_ans = n_ans - t

        if duree_restante_ans <= 0:
            prov = 0.0
        else:
            crd_restant = crd_mensuel[mois_ecoule: mois_ecoule + duree_restante_ans * 12]
            prov = calculer_prime_inventaire_seule(
                age_atteint, crd_restant, taux_tech, g, dict_Lx, dict_dx1
            )

        crd_t = float(crd_mensuel[mois_ecoule]) if mois_ecoule < len(crd_mensuel) else 0.0
        lignes_provisions.append({
            "Année (t)": t,
            "Âge Atteint": age_atteint,
            "CRD": round(crd_t, 2),
            "Provision Mathématique": round(prov, 3),
        })

    return primes, lignes_provisions
