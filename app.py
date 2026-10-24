for lien in liens_zip:
        df_zip = telecharger_et_extraire_zip(lien)
        if df_zip is not None:
            df_total = pd.concat([df_total, df_zip], ignore_index=True, sort=False)
    # Supprimer doublons globaux
    df_total.drop_duplicates(inplace=True)
    df_total.reset_index(drop=True, inplace=True)
    if df_total.empty:
        st.error("Aucune donnée chargée depuis les archives.")
        return None
    # Normaliser les colonnes (exemple : standardiser en minuscules, enlever espaces)
    df_total.columns = [str(col).strip().lower().replace(' ', '_') for col in df_total.columns]
    st.success(f"{len(df_total)} lignes chargées depuis les archives officielles.")
    return df_total

# ===== Fonctions d'analyse statistique =====
def calculer_frequences(df, colonnes_numeros):
    """
    Calcule la fréquence d'apparition des numéros dans les colonnes spécifiées.
    Retourne un DataFrame {'numéro','occurrences','fréquence (%)'} trié.
    """
    if not colonnes_numeros or df is None:
        return None
    serie = pd.concat([pd.to_numeric(df[c], errors='coerce') for c in colonnes_numeros],
                      ignore_index=True).dropna().astype(int)
    compte = serie.value_counts().sort_index()
    total = compte.sum()
    stats = pd.DataFrame({
        "Numéro": compte.index,
        "Occurrences": compte.values,
        "Fréquence (%)": (compte.values / total * 100).round(3)
    })
    stats.sort_values(by=["Occurrences","Numéro"], ascending=[False,True], inplace=True)
    return stats

def calculer_retards(df, colonnes_numeros):
    """
    Calcule le nombre de tirages depuis la dernière apparition de chaque numéro.
    Renvoie une série {numéro: retards}. Utile pour la stratégie 'retard'.
    """
    if not colonnes_numeros or df is None:
        return {}
    df_numeric = pd.concat([pd.to_numeric(df[c], errors='coerce') for c in colonnes_numeros],
                           ignore_index=True).dropna().astype(int)
    derniers = {}
    historique = list(df_numeric)  # de l'archive, du plus ancien au plus récent
    pour_i = {}
    for num in sorted(df_numeric.unique()):
        pour_i[num] = len(historique) - 1 - (len(historique) - 1 - historique[::-1].index(num)) \
                       if num in historique else None
        derniers[num] = pour_i[num] if pour_i[num] is not None else len(historique)
    # On renvoie la distance en tirages depuis la dernière sortie : plus c'est grand, plus il est 'en retard'
    retards = {num: len(historique) - 1 - idx for num, idx in zip(df_numeric.unique(), 
                 [len(historique) - 1 - historique[::-1].index(num) for num in df_numeric.unique()])}
    return retards

def generer_grille_aleatoire(jeu):
    """
    Génère une grille aléatoire valide.
    """
    if jeu == "EuroMillions":
        nums = sorted(random.sample(range(1,51), 5))
        étoiles = sorted(random.sample(range(1,13), 2))
    else:  # Loto français
        nums = sorted(random.sample(range(1,50), 5))
        étoiles = [random.randint(1,10)]
    return nums, étoiles

def generer_grille_frequence(stats, jeu):
    """
    Génère une grille en prenant les numéros les plus fréquents.
    stats : DataFrame de fréquences calculé par calculer_frequences.
    """
    if stats is None:
        return generer_grille_aleatoire(jeu)
    meilleurs = stats["Numéro"].tolist()
    if jeu == "EuroMillions":
        return sorted(meilleurs[:5]), sorted(meilleurs[-2:])  # top5 et 2 plus rares comme étoiles (exemple)
    else:
        return sorted(meilleurs[:5]), [meilleurs[-1]]  # top5 et 1 plus rare comme numéro chance

def generer_grille_retard(retards, jeu):
    """
    Génère une grille en choisissant les numéros ayant les plus grands retards.
    retards : dict {num: tirages depuis dernière apparition}.
    """
    if not retards:
        return generer_grille_aleatoire(jeu)
    nums_sorted = sorted(retards.items(), key=lambda x: x[1], reverse=True)
    numeros = [n for n,_ in nums_sorted][:5]
    etoiles = []
    if jeu == "EuroMillions":
        # Réutiliser la logique (étoiles = 2 plus 'en retard', si on avait séparé colonnes étoiles)
        etoiles = sorted(random.sample(range(1,13), 2))
    else:
        etoiles = [random.randint(1,10)]
    return sorted(numeros), etoiles

# On pourrait ajouter ici des générateurs basés sur paires fréquentes, modèle bayésien, apprentissage supervisé, etc.
# Pour le moment, on montre des fonctions de base. Les stratégies avancées peuvent être intégrées sur le même principe.

# ===== Intégration dans l’interface Streamlit (onglet “Generateur”) =====
with st.expander("🧠 Générateur de grilles avancé", expanded=True):
    st.write("Utilise différentes stratégies statistiques pour générer des grilles et afficher des explications.")
    nb = st.slider("Nombre de grilles à générer", 1, 10, 3, key="n_grilles", help="Combien de combinaisons proposer à la fois")
    strat = st.selectbox("Méthode de génération", ["Aléatoire", "Fréquence", "Retard"], key="strat_gen")
    if st.button("🎯 Générer des grilles"):
        if df is None:
            st.error("Aucune donnée chargée. Importez les archives avant de générer.")
        else:
            # Séparer numéros principaux et étoiles/bonus selon l'onglet Fréquences
            nums_cols = st.session_state.get("colonnes_numeros", [])
            bonus_cols = st.session_state.get("colonnes_bonus", [])
            # Calcul préliminaire
            stats_num = calculer_frequences(df, nums_cols)
            stats_bonus = calculer_frequences(df, bonus_cols)
            retards = calculer_retards(df, nums_cols)
            # Générer selon la stratégie choisie
            for i in range(nb):
                if strat == "Aléatoire":
                    nums, étoiles = generer_grille_aleatoire(jeu)
                elif strat == "Fréquence":
                    nums, étoiles = generer_grille_frequence(stats_num, jeu)
                else:  # "Retard"
                    nums, étoiles = generer_grille_retard(retards, jeu)
                st.markdown(f"**Grille {i+1} :** Numéros = {', '.join(map(str, nums))} · Étoiles/Chance = {', '.join(map(str, étoiles))}")
                # Explications chiffrées (exemples génériques)
                if strat == "Aléatoire":
