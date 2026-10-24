
import streamlit as st
import numpy as np

st.set_page_config(page_title="MonIA", page_icon="🎯")

st.title("🎯 MonIA")
st.subheader("Assistant statistique Loto et EuroMillions")

st.write(
    "Bienvenue ! Cette première version permet de générer "
    "des grilles aléatoires."
)

st.info(
    "Les tirages sont aléatoires. Aucune grille ne garantit "
    "un gain ni ne prédit les prochains numéros."
)

jeu = st.selectbox(
    "Choisis ton jeu",
    ["EuroMillions", "Loto français"]
)

nombre_grilles = st.slider(
    "Combien de grilles veux-tu générer ?",
    1, 10, 3
)

if st.button("Générer mes grilles"):
    for i in range(nombre_grilles):
        if jeu == "EuroMillions":
            numeros = sorted(
                np.random.choice(
                    range(1, 51), 5, replace=False
                ).tolist()
            )
            etoiles = sorted(
                np.random.choice(
                    range(1, 13), 2, replace=False
                ).tolist()
            )
            st.write(
                f"Grille {i + 1} : {numeros} ⭐ {etoiles}"
            )
        else:
            numeros = sorted(
                np.random.choice(
                    range(1, 50), 5, replace=False
                ).tolist()
            )
            chance = int(np.random.randint(1, 11))
            st.write(
                f"Grille {i + 1} : {numeros} 🍀 Chance : {chance}"
            )

st.caption("MonIA — version 1")
