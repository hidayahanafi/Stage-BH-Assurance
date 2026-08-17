import pandas as pd
import plotly.express as px
import streamlit as st

import config
from actuariat import simuler_contrat_complet

# --- Configuration de la page ---
st.set_page_config(page_title="Simulateur ADE BH Assurance", layout="wide", page_icon="🏦")

# --- Design minimaliste (CSS custom) ---
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    div[data-testid="stMetricValue"] {
        font-size: 1.8rem;
        font-weight: 300;
        color: #1e293b;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 0.85rem;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-weight: 500;
    }

    .stButton>button {
        border-radius: 6px;
        font-weight: 500;
        border: 1px solid #e2e8f0;
        background-color: #ffffff;
        color: #0f172a;
        transition: all 0.2s ease;
    }
    .stButton>button:hover {
        border-color: #3b82f6;
        color: #3b82f6;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data
def load_data():
    try:
        primes = pd.read_excel(config.FICHIER_PRIMES_SORTIE)
        provisions = pd.read_excel(config.FICHIER_PROVISIONS_SORTIE)
        primes["num_contrat"] = primes["num_contrat"].astype(str)
        provisions["num_contrat"] = provisions["num_contrat"].astype(str)
        return primes, provisions
    except Exception as e:
        st.error(f"Erreur de chargement des données. Avez-vous exécuté les scripts Python ? ({e})")
        return None, None


@st.cache_data
def load_td99(abattement: float = config.ABATTEMENT_MORTALITE):
    try:
        df_mortalite = pd.read_excel(config.FICHIER_MORTALITE)
        df_mortalite.columns = df_mortalite.columns.str.strip()
        df_mortalite = df_mortalite.sort_values(by="Age")

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
        return dict_Lx, dict_dx1
    except Exception:
        st.error("Erreur de chargement de la table TD 99.")
        return None, None


def _style_ligne(fig, titre: str, y_label: str):
    fig.update_traces(line_color="#3b82f6", marker=dict(size=6), line=dict(width=2))
    fig.update_layout(
        title=titre,
        template="plotly_white",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=40, b=0),
        xaxis=dict(showgrid=False, title_font=dict(size=12, color="#64748b")),
        yaxis=dict(showgrid=True, gridcolor="#f1f5f9", title_font=dict(size=12, color="#64748b")),
    )
    return fig


# --- Interface utilisateur ---
st.title("🏦 Tableau de Bord - Simulateur ADE")
st.sidebar.title("Navigation")
page = st.sidebar.radio("Aller à :", ["🔍 Recherche de contrat", "✨ Nouvelle Simulation"])

if page == "🔍 Recherche de contrat":
    st.header("Rechercher un contrat existant")

    primes, provisions = load_data()

    if primes is not None and provisions is not None:
        search_query = st.text_input("Entrez le numéro du contrat :")

        if search_query:
            contrat_prime = primes[primes["num_contrat"] == search_query]

            if not contrat_prime.empty:
                st.success("Contrat trouvé !")
                c_data = contrat_prime.iloc[0]

                st.subheader("📋 Informations du contrat")
                col1, col2, col3 = st.columns(3)
                col1.metric("Âge à la souscription", f"{c_data['Age_Souscription']} ans")
                col2.metric("Capital Emprunté", f"{c_data['montant_credit_normal']:,.2f} DT")
                col3.metric("Durée", f"{c_data['duree_contrat']} mois")

                st.subheader("💰 Tarification")
                col1, col2, col3 = st.columns(3)
                col1.metric("Prime Unique Pure", f"{c_data['Prime_Unique_Pure_Calculee']:,.2f} DT")
                col2.metric("Prime d'Inventaire", f"{c_data['Prime_Inventaire']:,.2f} DT")
                col3.metric("Prime Commerciale", f"{c_data['Prime_Commerciale']:,.2f} DT")

                st.subheader("📉 Évolution des Provisions Mathématiques")
                contrat_prov = provisions[provisions["num_contrat"] == search_query]

                if not contrat_prov.empty:
                    fig = px.line(
                        contrat_prov, x="t", y="Provision_t", markers=True,
                        labels={"t": "Année (t)", "Provision_t": "Provision (DT)"},
                    )
                    fig = _style_ligne(fig, f"Trajectoire de la Provision (Contrat {search_query})", "Provision (DT)")
                    st.plotly_chart(fig, width="stretch")

                    with st.expander("Voir les données détaillées (Provisions)"):
                        st.dataframe(contrat_prov)
                else:
                    st.warning("Aucune donnée de provision trouvée pour ce contrat.")
            else:
                st.error("Contrat introuvable dans la base.")

elif page == "✨ Nouvelle Simulation":
    st.header("Simuler un nouveau contrat")

    dict_Lx, dict_dx1 = load_td99()

    if dict_Lx is not None:
        with st.form("sim_form"):
            col1, col2, col3 = st.columns(3)
            age = col1.number_input("Âge à la souscription", min_value=18, max_value=85, value=35)
            capital = col2.number_input("Montant du crédit (DT)", min_value=1000, value=50000, step=5000)
            duree = col3.number_input("Durée du contrat (mois)", min_value=12, max_value=360, value=120, step=12)

            st.markdown("---")
            st.markdown("#### Paramètres Techniques")
            col4, col5, col6 = st.columns(3)
            taux_p = col4.number_input("Taux de crédit", value=0.07, format="%.3f")
            taux_tech = col5.number_input("Taux d'actualisation", value=0.03, format="%.3f")
            taux_abattement = col6.number_input(
                "Abattement Mortalité (%)", value=40, min_value=0, max_value=100
            ) / 100.0

            submit = st.form_submit_button("Lancer la simulation 🚀")

        if submit:
            with st.spinner("Calcul actuariel en cours..."):
                g = config.TAUX_CHARGEMENT_GESTION
                alpha = config.TAUX_CHARGEMENT_ACQUISITION

                # Recharge la table avec le nouvel abattement si besoin
                dict_Lx, dict_dx1 = load_td99(abattement=taux_abattement)

                primes, lignes_provisions = simuler_contrat_complet(
                    age, capital, duree, taux_p, taux_tech, g, alpha, dict_Lx, dict_dx1
                )

                if primes is None:
                    st.error("Impossible de simuler ce contrat (âge hors table de mortalité ?).")
                else:
                    st.success("Simulation terminée avec succès !")

                    st.subheader("💰 Tarification")
                    col_a, col_b, col_c = st.columns(3)
                    col_a.metric("Prime Unique Pure", f"{primes.prime_unique_pure:,.2f} DT")
                    col_b.metric("Prime d'Inventaire", f"{primes.prime_inventaire:,.2f} DT")
                    col_c.metric("Prime Commerciale", f"{primes.prime_commerciale:,.2f} DT")

                    st.subheader("📉 Évolution des Provisions Mathématiques")
                    df_prov = pd.DataFrame(lignes_provisions)
                    fig = px.line(
                        df_prov, x="Année (t)", y="Provision Mathématique", markers=True,
                    )
                    fig = _style_ligne(fig, "Trajectoire simulée de la Provision", "Provision Mathématique")
                    st.plotly_chart(fig, width="stretch")

                    st.dataframe(df_prov, width="stretch")
