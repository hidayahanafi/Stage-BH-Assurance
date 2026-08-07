import pandas as pd
import numpy as np

# 1. Chargement et préparation des données
df = pd.read_excel('prod_TDD.xlsx')
df_td99 = pd.read_excel('TD 99.xlsx')

colonnes_dates = ['DATE_NAISSANCE', 'EFFET_CONTRAT', 'EXPIRATION_CREDIT_NORMAL', 'DATE_SORTIE_RISQUE']
for col in colonnes_dates:
    df[col] = pd.to_datetime(df[col], errors='coerce')

df = df.dropna(subset=['DATE_NAISSANCE', 'EFFET_CONTRAT'])

# Probabilité théorique de décès (TD 99)
df_td99['qx_theorique'] = df_td99['dx1'] / df_td99['Lx']

# 2. Calcul vectorisé (Présence = Exposition)
annees_exercice = [2020, 2021, 2022, 2023, 2024]
df_list = []

for annee in annees_exercice:
    debut_annee = pd.to_datetime(f'{annee}-01-01')
    fin_annee = pd.to_datetime(f'{annee}-12-31')

    mask_actif = df['EFFET_CONTRAT'] <= fin_annee
    df_annee = df[mask_actif].copy()

    if df_annee.empty: continue

    # Dates d'entrée et sortie de l'exercice
    entree_risque = np.maximum(df_annee['EFFET_CONTRAT'], debut_annee)
    sorties_df = df_annee[['EXPIRATION_CREDIT_NORMAL', 'DATE_SORTIE_RISQUE']].fillna(pd.to_datetime('2100-01-01'))
    sortie_min_series = sorties_df.min(axis=1)
    sortie_risque = np.minimum(sortie_min_series, fin_annee)

    # Calcul de la présence (fraction d'année) et de l'âge
    exposition = (sortie_risque - entree_risque).dt.days / 365.25
    age_exercice = annee - df_annee['DATE_NAISSANCE'].dt.year

    mask_valide = (entree_risque <= sortie_risque) & (age_exercice >= 18) & (age_exercice <= 85)
    df_valide = df_annee[mask_valide].copy()
    
    if df_valide.empty: continue
        
    df_valide['EXERCICE'] = annee
    df_valide['AGE'] = age_exercice[mask_valide]
    df_valide['PRESENCE'] = exposition[mask_valide]  # Ce que l'Excel appelle "Présence"
    
    # Décès observés
    df_valide['DECES_REELS'] = np.where(
        df_valide['DATE_SORTIE_RISQUE'].notna() & (df_valide['DATE_SORTIE_RISQUE'].dt.year == annee),
        1, 0
    )

    df_list.append(df_valide[['EXERCICE', 'AGE', 'PRESENCE', 'DECES_REELS']])

df_sim = pd.concat(df_list, ignore_index=True)

# 3. Rapprochement avec la Table TD 99 pour obtenir les Décès TD
df_sim = pd.merge(df_sim, df_td99[['Age', 'qx_theorique']], left_on='AGE', right_on='Age', how='left')
df_sim['DECES_TD'] = df_sim['PRESENCE'] * df_sim['qx_theorique']

# 4. Tranches d'âge de l'étude (18-34, 35-59, >=60)
bins = [17, 34, 59, 120]
labels = ['18 à 34 ans', '35 à 59 ans', '>= 60 ans']
df_sim['TRANCHE_AGE'] = pd.cut(df_sim['AGE'], bins=bins, labels=labels, right=True)

# 5. Agrégation finale des tableaux de reporting
tableau_final = df_sim.groupby('TRANCHE_AGE', observed=False).agg(
    PRESENCE=('PRESENCE', 'sum'),
    DECES_OBSERVES=('DECES_REELS', 'sum'),
    DECES_TD=('DECES_TD', 'sum')
).reset_index()

# 6. Intégration des sinistres TARDIFS 
coef_tardifs_par_tranche = {
    '18 à 34 ans': 1.05, 
    '35 à 59 ans': 1.04, 
    '>= 60 ans': 1.03
}

# SOLUTION : On convertit la tranche en texte pour le map, puis le résultat en float
tableau_final['COEF_TARDIF'] = tableau_final['TRANCHE_AGE'].astype(str).map(coef_tardifs_par_tranche).astype(float)

# Maintenant le calcul mathématique va passer sans problème !
tableau_final['NB_TARDIFS'] = tableau_final['DECES_OBSERVES'] * (tableau_final['COEF_TARDIF'] - 1)

# Décès ajustés = Observés + Tardifs
tableau_final['DECES_AJUSTES'] = tableau_final['DECES_OBSERVES'] + tableau_final['NB_TARDIFS']

# Comparatif Taux de Décès
tableau_final['TAUX_DECES_REEL'] = tableau_final['DECES_AJUSTES'] / tableau_final['PRESENCE']
tableau_final['TAUX_DECES_THEORIQUE'] = tableau_final['DECES_TD'] / tableau_final['PRESENCE']
tableau_final['RATIO_REEL_SUR_THEORIQUE'] = tableau_final['TAUX_DECES_REEL'] / tableau_final['TAUX_DECES_THEORIQUE']

print("\n--- TABLEAU COMPARATIF FINAL (2020 - 2024) ---")
colonnes_a_afficher = ['TRANCHE_AGE', 'PRESENCE', 'DECES_OBSERVES', 'NB_TARDIFS', 'DECES_AJUSTES', 'DECES_TD', 'TAUX_DECES_REEL', 'TAUX_DECES_THEORIQUE']
print(tableau_final[colonnes_a_afficher].to_string(index=False))

# Exportation Excel
tableau_final.to_excel('Analyse_Mortalite_Tranches_Tardifs.xlsx', index=False)