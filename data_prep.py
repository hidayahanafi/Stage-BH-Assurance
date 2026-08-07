import pandas as pd
import numpy as np

import pandas as pd
import numpy as np

def charger_et_nettoyer_donnees(chemin_contrats, chemin_td99):
    """
    Importe, nettoie et prépare les bases de données pour le simulateur PM.
    """
    print(" Chargement des fichiers Excel en cours...")
    
    try:
        df_contrats = pd.read_excel(chemin_contrats)
        df_mortalite = pd.read_excel(chemin_td99)
    except FileNotFoundError as e:
        print(f" Erreur : Fichier introuvable. Vérifie tes chemins. Détails : {e}")
        return None, None, None

    # Nettoyage des noms de colonnes
    df_contrats.columns = df_contrats.columns.str.strip().str.lower()
    df_mortalite.columns = df_mortalite.columns.str.strip() 

    # Transformation de la table TD99 en dictionnaires
    # On utilise Lx (survivants bruts) et dx1 (décès bruts) — sans actualisation intégrée
    # Dx et Cx sont déjà actualisés à 3% dans la table, ce qui créerait une double
    # actualisation si on les combine au taux propre de chaque contrat.
    df_mortalite = df_mortalite.sort_values(by='Age')
    
    # --- ABATTEMENT MORTALITÉ (40%) ---
    # La table TD 99 est ancienne. On réduit la mortalité de 40% pour refléter la réalité.
    abattement = 0.40
    df_mortalite['qx'] = df_mortalite['dx1'] / df_mortalite['Lx']
    df_mortalite['qx_abattu'] = df_mortalite['qx'] * (1 - abattement)
    
    # Reconstitution de la table avec une population initiale de 100 000
    l_x_courant = 100000.0
    nouveaux_Lx = []
    nouveaux_dx = []
    for qx_new in df_mortalite['qx_abattu']:
        nouveaux_Lx.append(l_x_courant)
        dx_new = l_x_courant * qx_new
        nouveaux_dx.append(dx_new)
        l_x_courant -= dx_new
        
    df_mortalite['Lx'] = nouveaux_Lx
    df_mortalite['dx1'] = nouveaux_dx
    
    dict_Lx  = df_mortalite.set_index("Age")["Lx"].to_dict()   # Survivants à x
    dict_dx1 = df_mortalite.set_index("Age")["dx1"].to_dict()  # Décès entre x et x+1

    # Typage des Dates
    colonnes_dates = [
        'date_naissance', 'effet_contrat', 'date_entree_risque', 
        'expiration', 'date_sortie_risque'
    ]
    for col in colonnes_dates:
        if col in df_contrats.columns:
            df_contrats[col] = pd.to_datetime(df_contrats[col], errors='coerce')

    # Typage des variables numériques
    colonnes_numeriques = [
        'montant_credit_normal', 'taux_interet_applique', 'taux_technique',
        'duree_contrat', 'duree_credit_normal', 'duree_garantie', 'quotite',
        'prime_nette'
    ]
    for col in colonnes_numeriques:
        if col in df_contrats.columns:
            df_contrats[col] = pd.to_numeric(df_contrats[col], errors='coerce')

    # Suppression des lignes inutilisables
    df_propres = df_contrats.dropna(subset=['date_naissance', 'montant_credit_normal', 'effet_contrat']).copy()

    # Calcul de l'âge à la souscription
    df_propres['Age_Souscription'] = df_propres['effet_contrat'].dt.year - df_propres['date_naissance'].dt.year

    # Filtrer les âges aberrants (ex: erreurs de saisie donnant des âges négatifs ou irréalistes)
    df_propres = df_propres[(df_propres['Age_Souscription'] >= 18) & (df_propres['Age_Souscription'] <= 85)]


    print("🔧 Application des règles métier :")
    print("   - Taux d'intérêt du crédit : 7% (0.07)")
    df_propres['taux_interet_applique'] = 0.07
    
    print("   - Taux technique (Note TD99) : 3% (0.03)")
    df_propres['taux_technique'] = 0.03
    
    print("   - Chargement gestion : 0,2‰ (0.0002)")
    df_propres['taux_chargement_gestion'] = 0.0002
    
    print("   - Chargement acquisition : 10% (0.10)")
    df_propres['taux_chargement_acquisition'] = 0.10
    
    # Standardisation de la Quotité (doit être entre 0 et 1)
    if 'quotite' in df_propres.columns:
        if df_propres['quotite'].max() > 1:
            df_propres['quotite'] = df_propres['quotite'] / 100.0

    print(f"🧹 Nettoyage terminé ! Nombre de contrats exploitables : {len(df_propres)}")
    

    from sklearn.experimental import enable_iterative_imputer  
    from sklearn.impute import IterativeImputer
    from sklearn.linear_model import BayesianRidge
    import numpy as np

    print(" 🤖 Traitement des durées via MICE (Iterative Imputer)...")
    
    # 1. Préparation de la cible (remplacer les <= 0 par NaN pour l'imputation)
    df_propres['duree_temporaire'] = df_propres['duree_contrat'].fillna(df_propres['duree_credit_normal'])
    df_propres.loc[df_propres['duree_temporaire'] <= 0, 'duree_temporaire'] = np.nan
    
    # 2. Sélection des features (X) pertinentes pour la régression
    # On utilise l'âge et le montant pour prédire la durée la plus probable
    features_imputation = ['Age_Souscription', 'montant_credit_normal', 'duree_temporaire']
    df_features = df_propres[features_imputation]
    
    # 3. Initialisation et entraînement du MICE
    # BayesianRidge est le modèle par défaut, excellent car il gère l'incertitude des prédictions
    imputer = IterativeImputer(estimator=BayesianRidge(), max_iter=10, random_state=42)
    
    print("    -> Entraînement du modèle et prédiction des durées en cours (cela peut prendre quelques secondes)...")
    df_imputed = pd.DataFrame(imputer.fit_transform(df_features), columns=features_imputation, index=df_propres.index)
    
    # 4. Récupération des prédictions, arrondies au mois entier
    df_propres['duree_contrat'] = df_imputed['duree_temporaire'].round().astype(int)
    
    nb_corriges = df_propres['duree_temporaire'].isna().sum()
    print(f"    -> {nb_corriges} contrats intelligemment corrigés par Machine Learning (MICE).")
    
    # Nettoyage de la colonne temporaire
    df_propres = df_propres.drop(columns=['duree_temporaire'])

    return df_propres, dict_Lx, dict_dx1
if __name__ == "__main__":
    fichier_contrats = 'prod_TDD.xlsx'
    fichier_mortalite = 'TD 99.xlsx' 

    print("Démarrage du pipeline de préparation des données...")
    df_portfolio, dict_Lx, dict_dx1 = charger_et_nettoyer_donnees(fichier_contrats, fichier_mortalite)

    if df_portfolio is not None:
        print("\n Aperçu des contrats après correction du taux :")
        colonnes_a_afficher = ['date_naissance', 'Age_Souscription', 'montant_credit_normal', 'taux_interet_applique']
        if 'num_contrat' in df_portfolio.columns:
            colonnes_a_afficher.insert(0, 'num_contrat')
            
        print(df_portfolio[colonnes_a_afficher].head())
        

        print("\n🔍 Lancement de l'audit des durées de contrats...")

        # 1. On crée une colonne temporaire qui fusionne les deux durées possibles
        df_portfolio['duree_mois_calculee'] = df_portfolio['duree_contrat'].fillna(df_portfolio['duree_credit_normal'])

        # 2. On filtre pour isoler les contrats où la durée est <= 0 ou manquante (NaN)
        contrats_invalides = df_portfolio[
            (df_portfolio['duree_mois_calculee'] <= 0) | 
            (df_portfolio['duree_mois_calculee'].isnull())
        ].copy()

        # 3. On sélectionne uniquement les colonnes pertinentes pour l'encadrant
        colonnes_audit = [
            "num_contrat", 
            "effet_contrat", 
            "montant_credit_normal",
            "duree_contrat", 
            "duree_credit_normal", 
            "duree_mois_calculee"
        ]

        # Sécurité : on ne garde que les colonnes qui existent vraiment dans la base
        colonnes_existantes = [col for col in colonnes_audit if col in contrats_invalides.columns]
        rapport_anomalies = contrats_invalides[colonnes_existantes]

        # 4. Affichage des statistiques
        nb_total = len(df_portfolio)
        nb_anomalies = len(rapport_anomalies)
        pourcentage = (nb_anomalies / nb_total) * 100

        print(f"\n--- DIAGNOSTIC DES DURÉES INVALIDES ---")
        print(f"Total des contrats analysés : {nb_total}")
        print(f"Contrats avec durée invalide (<= 0 ou vide) : {nb_anomalies}")
        print(f"Proportion : {pourcentage:.2f}% de la base\n")

        # 5. Exportation du rapport s'il y a des anomalies
        if nb_anomalies > 0:
            fichier_export = "Audit_Anomalies_Durees.xlsx"
            rapport_anomalies.to_excel(fichier_export, index=False)
            print(f" Fichier '{fichier_export}' généré avec succès dans le dossier !")
        else:
            print(" Parfait ! Aucune durée invalide détectée dans la base.")