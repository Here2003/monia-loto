
import random
from collections import Counter

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="MonIA - Analyse EuroMillions",
    page_icon="🎱",
    layout="wide",
)

st.title("🎱 MonIA — Laboratoire EuroMillions")
st.write(
    "Analyse les anciens tirages et génère des grilles "
    "pour tes propres études statistiques."
)

st.warning(
    "Les tirages sont aléatoires. Les statistiques passées "
    "ne permettent pas de prédire le prochain résultat."
)

st.header("1. Analyser les anciens tirages")

st.write(
    "Importe un fichier CSV contenant les colonnes "
    "n1, n2, n3, n4, n5, e1 et e2."
)

fichier = st.file_uploader(
    "Choisir un fichier CSV",
    type=["csv"],
)

if fichier is not None:
    try:
        df = pd.read_csv(fichier)
        df.columns = df.columns.str.strip().str.lower()

        colonnes_n = ["n1", "n2", "n3", "n4", "n5"]
        colonnes_e = ["e1", "e2"]
        colonnes = colonnes_n + colonnes_e

        if not set(colonnes).issubset(df.columns):
            st.error(
                "Colonnes requises : n1, n2, n3, n4, n5, e1, e2."
            )
        else:
            df = df.dropna(subset=colonnes).copy()

            for c in colonnes:
                df[c] = pd.to_numeric(df[c], errors="coerce")

            df = df.dropna(subset=colonnes)

            valides = (
                df[colonnes_n].apply(
                    lambda ligne: (
                        ligne.between(1, 50).all()
                        and ligne.nunique() == 5
                    ),
                    axis=1,
                )
                & df[colonnes_e].apply(
                    lambda ligne: (
                        ligne.between(1, 12).all()
                        and ligne.nunique() == 2
                    ),
                    axis=1,
                )
            )

            df = df[valides].copy()

            if df.empty:
                st.error("Aucun tirage valide trouvé dans ce fichier.")
            else:
                st.success(
                    f"{len(df)} tirages valides analysés."
                )

                frequences_n = Counter(
                    df[colonnes_n].to_numpy().flatten().astype(int)
                )
                frequences_e = Counter(
                    df[colonnes_e].to_numpy().flatten().astype(int)
                )

                gauche, droite = st.columns(2)

                with gauche:
                    st.subheader("Fréquence des numéros")
                    tableau_n = pd.DataFrame(
                        [
                            {
                                "Numéro": n,
                                "Occurrences": frequences_n[n],
                            }
                            for n in range(1, 51)
                        ]
                    )
                    st.bar_chart(
                        tableau_n.set_index("Numéro")
                    )

                with droite:
                    st.subheader("Fréquence des étoiles")
                    tableau_e = pd.DataFrame(
                        [
                            {
                                "Étoile": n,
                                "Occurrences": frequences_e[n],
                            }
                            for n in range(1, 13)
                        ]
                    )
                    st.bar_chart(
                        tableau_e.set_index("Étoile")
                    )

                st.subheader("Les 10 numéros les plus fréquents")
                st.dataframe(
                    tableau_n.sort_values(
                        "Occurrences", ascending=False
                    ).head(10),
                    hide_index=True,
                    use_container_width=True,
                )

                st.subheader("Les étoiles les plus fréquentes")
                st.dataframe(
                    tableau_e.sort_values(
                        "Occurrences", ascending=False
                    ),
                    hide_index=True,
                    use_container_width=True,
                )

    except Exception as erreur:
        st.error(f"Impossible de lire ce fichier : {erreur}")

st.divider()

st.header("2. Générer des grilles")

nombre = st.slider(
    "Nombre de grilles à générer",
    min_value=1,
    max_value=20,
    value=5,
)

if st.button("🎲 Générer mes grilles"):
    grilles = set()

    while len(grilles) < nombre:
        numeros = tuple(
            sorted(random.sample(range(1, 51), 5))
        )
        etoiles = tuple(
            sorted(random.sample(range(1, 13), 2))
        )
        grilles.add((numeros, etoiles))

    for i, (numeros, etoiles) in enumerate(
        sorted(grilles), start=1
    ):
        st.write(
            f"**Grille {i} :** "
            f"{' – '.join(map(str, numeros))} "
            f"⭐ {etoiles[0]} et {etoiles[1]}"
        )

    st.caption(
        "Chaque combinaison valide a la même probabilité "
        "de jackpot : 1 sur 139 838 160 selon les règles "
        "actuelles du jeu."
    )

st.divider()
st.caption("MonIA — Outil d'analyse statistique, sans garantie de gain.")
