min_value=1, max_value=max(1, min(1000, len(df))),
                value=min(100, len(df)),
            )
            paires = calculer_paires(df.tail(n_recent), cols)
            st.dataframe(paires, hide_index=True, use_container_width=True)
            st.caption("Ces paires sont des associations observées, pas une prédiction du prochain tirage.")

with onglets[3]:
    st.header("Gains et gagnants publiés")
    if df is None:
        st.info("Importe une archive qui contient des données de gains ou de gagnants.")
    else:
        candidats = [
            c for c in df.columns
            if any(m in nom_normalise(c) for m in (
                "gain", "rapport", "jackpot", "lot", "gagnant",
                "winner", "prize", "rang", "montant",
            ))
        ]
        if candidats:
            st.write("Colonnes potentiellement liées aux gains :")
            st.write(candidats)
            st.dataframe(df[candidats].head(100), use_container_width=True)
            st.warning("Vérifie les intitulés et les unités avant toute interprétation : gagnants, gain individuel et montant total sont différents.")
        else:
            st.info("Aucune colonne de gains/gagnants détectée dans les fichiers importés.")

with onglets[4]:
    st.header("Probabilités théoriques")
    if jeu == "EuroMillions":
        total = math.comb(50, 5) * math.comb(12, 2)
        st.write("Grille simple : 5 numéros parmi 50 et 2 étoiles parmi 12.")
    else:
        total = math.comb(49, 5) * 10
        st.write("Grille simple du Loto actuel : 5 numéros parmi 49 et 1 numéro Chance parmi 10.")
    st.metric("Probabilité théorique du jackpot", f"1 sur {total:,}")
    st.caption("Calcul pour les règles indiquées, pas nécessairement applicables à toutes les périodes historiques.")
    st.markdown(
        "**À retenir :** dans un tirage équitable, chaque combinaison valide a la même probabilité. "
        "Les fréquences passées ne rendent pas un numéro « dû »."
    )

with onglets[5]:
    st.header("Explorateur des archives")
    if df is None:
        st.info("Aucune archive chargée.")
    else:
        schema = pd.DataFrame({
            "Colonne": df.columns,
            "Type": [str(t) for t in df.dtypes],
            "Valeurs présentes": [int(df[c].notna().sum()) for c in df.columns],
            "Valeurs manquantes": [int(df[c].isna().sum()) for c in df.columns],
        })
        st.dataframe(schema, hide_index=True, use_container_width=True)
        st.download_button(
            "Télécharger les données combinées (CSV)",
            data=df.to_csv(index=False).encode("utf-8-sig"),
            file_name="monia_donnees_combinees.csv",
            mime="text/csv",
        )
    st.divider()
    st.write("### Vérifier l'accès aux pages officielles")
    st.caption("Ce test vérifie l'accès à la page FDJ, mais ne télécharge pas automatiquement les archives.")
    if st.button("Tester la page officielle FDJ"):
        with st.spinner("Vérification de l'accès à la page officielle…"):
            try:
                url_finale, statut, _ = charger_page_fdj(URLS_FDJ[jeu])
                st.success(f"Page accessible (HTTP {statut}) : {url_finale}")
                st.info("La page est accessible. L'extraction automatique des liens d'archives devra être validée séparément.")
            except Exception as exc:
                st.error(f"Page non accessible depuis l'application : {exc}")

st.divider()
st.header("🧠 Néréon — analyse autonome")
if df is None:
    st.info("Importe une archive pour que Néréon puisse analyser des données réelles.")
else:
    if st.button("🔬 Analyser automatiquement les données", type="primary"):
        colonnes_num = st.session_state.get("colonnes_numeros", [])
        colonnes_bonus = st.session_state.get("colonnes_bonus", [])
        if not colonnes_num:
            st.warning("Ouvre d'abord l'onglet Fréquences et vérifie les colonnes des numéros principaux.")
        else:
            with st.spinner("Contrôle des données et calcul des statistiques…"):
                stats = calculer_frequences(df, colonnes_num, 1, 50 if jeu == "EuroMillions" else 49)
                paires = calculer_paires(df, colonnes_num, 10)
                retards = calculer_retards_par_tirage(df, colonnes_num, 1, 50 if jeu == "EuroMillions" else 49)
                invalides = verifier_lignes(df, colonnes_num, 5)
            st.subheader("1. Résumé des données")
            st.write(f"Jeu sélectionné : **{jeu}**")
            st.write(f"Lignes disponibles : **{len(df)}**")
            st.write(f"Colonnes principales analysées : **{', '.join(colonnes_num)}**")
            st.write(f"Lignes présentant une anomalie de nombre de numéros ou un doublon interne : **{len(invalides)}**")
            st.subheader("2. Fréquences principales")
            st.dataframe(stats, hide_index=True, use_container_width=True)
            st.subheader("3. Paires les plus observées")
            st.dataframe(paires, hide_index=True, use_container_width=True)
            st.subheader("4. Retards observés")
            st.dataframe(retards, hide_index=True, use_container_width=True)
            if colonnes_bonus:
                st.subheader("5. Fréquences bonus séparées")
                stats_bonus = calculer_frequences(
                    df, colonnes_bonus, 1, 12 if jeu == "EuroMillions" else 10
                )
                st.dataframe(stats_bonus, hide_index=True, use_container_width=True)
            st.subheader("Conclusion de Néréon")
            st.write(
                "Cette analyse décrit les archives chargées. Les résultats dépendent du choix des colonnes, "
                "de la période et de l'ordre des lignes. Les fréquences, retards et paires ne prouvent pas "
                "qu'une combinaison sera plus susceptible de sortir au prochain tirage."
            )
            if invalides:
                st.warning("Certaines lignes doivent être vérifiées. Les règles et formats peuvent varier selon la période.")
            else:
                st.success("Aucune anomalie simple de nombre de numéros ou de répétition interne détectée dans les lignes analysées.")

st.caption(
    "MonIA — Néréon | Analyses descriptives reproductibles. "
    "Les sources externes ne sont considérées comme consultées qu'après un accès effectif."
)
