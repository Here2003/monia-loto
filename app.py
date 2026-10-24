return pd.DataFrame(
            columns=["Numéro", "Retard (tirages)"]
        )

    presents = set(serie)
    maximum = max(presents)

    resultat = []

    for numero in range(1, maximum + 1):
        retard = 0

        for valeur in reversed(serie):
            if valeur == numero:
                break
            retard += 1

        resultat.append({
            "Numéro": numero,
            "Retard (tirages)": (
                retard if numero in presents else len(serie)
            ),
        })

    return pd.DataFrame(resultat).sort_values(
        "Retard (tirages)", ascending=False
    ).reset_index(drop=True)

# --------------------------------------------------
# Préparation des données
# --------------------------------------------------

df = None
if tables:
    df = pd.concat(
        [table for _, table in tables],
        ignore_index=True,
        sort=False,
    )
    df = df.drop_duplicates().reset_index(drop=True)

if df is not None:
    st.success(
        f"{len(tables)} table(s) lue(s) · "
        f"{len(df):,} lignes · {len(df.columns)} colonnes"
    )

    with st.expander("Examiner les colonnes de l'archive"):
        st.write(list(df.columns))
        st.dataframe(df.head(10), use_container_width=True)

# --------------------------------------------------
# Onglets
# --------------------------------------------------

onglets = st.tabs([
    "🏠 Tableau de bord",
    "🔢 Fréquences",
    "⚪ Combinaisons",
    "💰 Gains et gagnants",
    "🎯 Probabilités",
    "📂 Archives",
])

# --------------------------------------------------
# 1. Tableau de bord
# --------------------------------------------------

with onglets[0]:
    st.header("Vue générale")
    if df is not None:
        c1, c2, c3 = st.columns(3)
        c1.metric("Lignes analysées", f"{len(df):,}")
        c2.metric("Colonnes disponibles", len(df.columns))
        c3.metric(
            "Lignes en double supprimées",
            sum(len(t) for _, t in tables) - len(df),
        )
        st.write("### Aperçu des données")
        st.dataframe(df.head(20), use_container_width=True)
        st.write("### Qualité des données")
        qualite = pd.DataFrame({
            "Indicateur": [
                "Valeurs manquantes",
                "Lignes entièrement vides",
                "Colonnes",
            ],
            "Résultat": [
                int(df.isna().sum().sum()),
                int(df.isna().all(axis=1).sum()),
                len(df.columns),
            ],
        })
        st.dataframe(qualite, hide_index=True, use_container_width=True)
    else:
        st.write(
            "Ce tableau affichera le volume d'archives, les périodes "
            "couvertes, la qualité des données et les indicateurs clés."
        )

# --------------------------------------------------
# 2. Fréquences des numéros
# --------------------------------------------------


# --------------------------------------------------
# 2. FREQUENCES DES NUMEROS ET DES ETOILES
# --------------------------------------------------

with onglets[1]:
    st.header("Fréquences et récurrences")

    if df is None:
        st.info("Importe les archives pour commencer l'analyse.")
    else:
        st.write(
            "Sélectionne séparément les colonnes des numéros principaux "
            "et celles des étoiles ou du numéro Chance."
        )

        colonnes_numeriques = [
            c for c in df.columns
            if pd.to_numeric(df[c], errors="coerce").notna().sum() > 0
        ]

        colonnes_num = st.multiselect(
            "Colonnes des numéros principaux",
            options=colonnes_numeriques,
            key="colonnes_numeros",
        )

        colonnes_bonus = st.multiselect(
            "Colonnes des étoiles / numéro Chance",
            options=[
                c for c in colonnes_numeriques if c not in colonnes_num
            ],
            key="colonnes_bonus",
        )

        def calculer_frequences(colonnes):
            if not colonnes:
                return None

            valeurs = pd.concat(
                [
                    pd.to_numeric(df[c], errors="coerce")
                    for c in colonnes
                ],
                ignore_index=True,
            ).dropna()

            valeurs = valeurs[valeurs % 1 == 0].astype(int)

            if valeurs.empty:
                return None

            compte = valeurs.value_counts().sort_index()

            resultat = pd.DataFrame({
                "Numéro": compte.index,
                "Occurrences": compte.values,
                "Fréquence (%)": (
                    compte.values / compte.sum() * 100
                ).round(3),
            })

            return resultat.sort_values(
                ["Occurrences", "Numéro"],
                ascending=[False, True],
            )

        for titre, colonnes in [
            ("Numéros principaux", colonnes_num),
            ("Étoiles / numéro Chance", colonnes_bonus),
        ]:
            st.subheader(titre)
            resultat = calculer_frequences(colonnes)

            if resultat is not None:
                gauche, droite = st.columns(2)
                gauche.metric(
                    "Valeurs comptées",
                    int(resultat["Occurrences"].sum()),
                )
                droite.metric(
                    "Valeurs distinctes",
                    len(resultat),
                )

                st.dataframe(
                    resultat,
                    hide_index=True,
