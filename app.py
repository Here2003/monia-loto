
import io
import random
import re
import zipfile
from collections import Counter
from datetime import datetime, timezone

import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup

st.set_page_config(
    page_title="MonIA — Loto et EuroMillions",
    page_icon="🎱",
    layout="wide",
)

SOURCES = {
    "EuroMillions": (
        "https://www.fdj.fr/jeux-de-tirage/"
        "euromillions-my-million/historique",
        50,
        12,
        5,
        2,
    ),
    "Loto français": (
        "https://www.fdj.fr/jeux-de-tirage/loto/historique",
        49,
        10,
        5,
        1,
    ),
}

HEADERS = {
    "User-Agent": "MonIA-Statistics/1.0 (public historical data)"
}


@st.cache_data(ttl=3600, show_spinner=False)
def telecharger_archives(url_page):
    """Repère et télécharge les archives ZIP liées à la page."""
    reponse = requests.get(
        url_page, headers=HEADERS, timeout=25
    )
    reponse.raise_for_status()

    soup = BeautifulSoup(reponse.text, "html.parser")
    liens = []

    for lien in soup.find_all("a", href=True):
        url = lien["href"].strip()

        if ".zip" not in url.lower():
            continue

        if url.startswith("//"):
            url = "https:" + url
        elif url.startswith("/"):
            url = "https://www.fdj.fr" + url
        elif not url.startswith("http"):
            continue

        if "fdj.fr" in url.lower():
            liens.append(url)

    archives = []
    erreurs = []

    for url in dict.fromkeys(liens):
        try:
            fichier = requests.get(
                url, headers=HEADERS, timeout=30
            )
            fichier.raise_for_status()

            with zipfile.ZipFile(io.BytesIO(fichier.content)) as z:
                for nom in z.namelist():
                    if nom.lower().endswith((".csv", ".txt")):
                        contenu = z.read(nom)
                        archives.append((nom, contenu))
        except Exception as erreur:
            erreurs.append(f"{url} : {erreur}")

    return archives, erreurs, len(liens)


def lire_table(contenu):
    """Essaie plusieurs encodages et séparateurs courants."""
    for encodage in ("utf-8-sig", "cp1252", "latin1"):
        for separateur in (";", ",", "\t"):
            try:
                df = pd.read_csv(
                    io.BytesIO(contenu),
                    sep=separateur,
                    encoding=encodage,
                    dtype=str,
                    on_bad_lines="skip",
                )
                if len(df.columns) >= 5 and not df.empty:
                    df.columns = [
                        str(c).strip().lower() for c in df.columns
                    ]
                    return df
            except Exception:
                pass
    return None


def trouver_colonne(df, motifs):
    for colonne in df.columns:
        nom = re.sub(r"[^a-z0-9]", "", colonne.lower())
        if any(motif in nom for motif in motifs):
            return colonne
    return None


def normaliser_archive(archives, jeu):
    """Convertit les formats reconnus en colonnes communes."""
    resultat = []
    erreurs = []

    if jeu == "EuroMillions":
        max_num, max_bonus, nb_num, nb_bonus = 50, 12, 5, 2
        motifs_num = [
            ("boule1", "numero1", "num1", "n1"),
            ("boule2", "numero2", "num2", "n2"),
            ("boule3", "numero3", "num3", "n3"),
            ("boule4", "numero4", "num4", "n4"),
            ("boule5", "numero5", "num5", "n5"),
        ]
        motifs_bonus = [
            ("etoile1", "star1", "e1"),
            ("etoile2", "star2", "e2"),
        ]
    else:
        max_num, max_bonus, nb_num, nb_bonus = 49, 10, 5, 1
        motifs_num = [
            ("boule1", "numero1", "num1", "n1"),
            ("boule2", "numero2", "num2", "n2"),
            ("boule3", "numero3", "num3", "n3"),
            ("boule4", "numero4", "num4", "n4"),
            ("boule5", "numero5", "num5", "n5"),
        ]
        motifs_bonus = [
            ("numerchance", "chance", "numerochance", "numchance")
        ]

    for nom, contenu in archives:
        df = lire_table(contenu)
        if df is None:
            erreurs.append(f"{nom} : format non reconnu")
            continue

        colonnes_n = [
            trouver_colonne(df, motifs) for motifs in motifs_num
        ]
        colonnes_b = [
            trouver_colonne(df, motifs) for motifs in motifs_bonus
        ]

        if any(c is None for c in colonnes_n + colonnes_b):
            erreurs.append(
                f"{nom} : noms de colonnes non reconnus"
            )
            continue

        date_col = trouver_colonne(
            df, ("date", "datetirage", "datedutirage")
        )

        for _, ligne in df.iterrows():
            try:
                numeros = [
                    int(float(ligne[c])) for c in colonnes_n
                ]
                bonus = [
                    int(float(ligne[c])) for c in colonnes_b
                ]

                if (
                    len(set(numeros)) != nb_num
                    or any(n < 1 or n > max_num for n in numeros)
                    or len(set(bonus)) != nb_bonus
                    or any(b < 1 or b > max_bonus for b in bonus)
                ):
                    continue

                date = str(ligne[date_col]) if date_col else ""
                resultat.append({
                    "date": date,
                    "nombres": sorted(numeros),
                    "bonus": sorted(bonus),
                    "source": nom,
                })
            except (ValueError, TypeError, KeyError):
                continue

    uniques = {}
    for tirage in resultat:
        cle = (
            tirage["date"],
            tuple(tirage["nombres"]),
            tuple(tirage["bonus"]),
        )
        uniques[cle] = tirage

    return list(uniques.values()), erreurs


def afficher_analyse(tirages, jeu):
    if not tirages:
        st.warning(
            "Aucun tirage reconnu. La structure des archives "
            "a peut-être changé : consulte les diagnostics ci-dessous."
        )
        return

    max_num = 50 if jeu == "EuroMillions" else 49
    max_bonus = 12 if jeu == "EuroMillions" else 10

    st.success(f"{len(tirages)} tirages valides analysés.")
    numeros = Counter()
    bonus = Counter()

    for tirage in tirages:
        numeros.update(tirage["nombres"])
        bonus.update(tirage["bonus"])

    gauche, droite = st.columns(2)

    with gauche:
        st.subheader("Fréquence des numéros")
        tableau = pd.DataFrame({
            "Numéro": range(1, max_num + 1),
            "Occurrences": [
                numeros[n] for n in range(1, max_num + 1)
            ],
        })
        st.bar_chart(tableau.set_index("Numéro"))
        st.dataframe(
            tableau.sort_values(
                "Occurrences", ascending=False
            ).head(10),
            hide_index=True,
            use_container_width=True,
        )

    with droite:
        st.subheader("Fréquence des numéros bonus")
        tableau_bonus = pd.DataFrame({
            "Bonus": range(1, max_bonus + 1),
            "Occurrences": [
                bonus[n] for n in range(1, max_bonus + 1)
            ],
        })
        st.bar_chart(tableau_bonus.set_index("Bonus"))
        st.dataframe(
            tableau_bonus.sort_values(
                "Occurrences", ascending=False
            ),
            hide_index=True,
            use_container_width=True,
        )

    st.subheader("Derniers tirages reconnus")
    st.dataframe(
        pd.DataFrame([
            {
                "Date": t["date"],
                "Numéros": " – ".join(map(str, t["nombres"])),
                "Bonus": " – ".join(map(str, t["bonus"])),
                "Archive": t["source"],
            }
            for t in tirages[-20:][::-1]
        ]),
        hide_index=True,
        use_container_width=True,
    )

    st.caption(
        "Les fréquences décrivent uniquement les données historiques. "
        "Elles ne prédisent pas les prochains résultats."
    )


st.title("🎱 MonIA")
st.subheader("Laboratoire statistique — Loto et EuroMillions")
st.write(
    "MonIA essaie de récupérer les archives publiques et "
    "d'analyser les données disponibles."
)
st.info(
    "Le hasard reste indépendant : aucun calcul ne garantit "
    "un gain ni ne permet de connaître les prochains numéros."
)

jeu = st.sidebar.selectbox(
    "Choisir un jeu", list(SOURCES.keys())
)

if st.sidebar.button("🔄 Actualiser les archives"):
    telecharger_archives.clear()

url, max_num, max_bonus, nb_num, nb_bonus = SOURCES[jeu]

with st.spinner("Recherche et téléchargement des archives officielles…"):
    try:
        archives, erreurs_reseau, nb_liens = telecharger_archives(url)
        tirages, erreurs_format = normaliser_archive(archives, jeu)

        st.caption(
            "Dernière tentative : "
            + datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
        )
        st.caption(
            f"Liens ZIP repérés : {nb_liens} · "
            f"Fichiers lus : {len(archives)}"
        )

        afficher_analyse(tirages, jeu)

        with st.expander("Diagnostics de récupération"):
            st.write(f"Archives téléchargées : {len(archives)}")
            st.write(f"Tirages reconnus : {len(tirages)}")
            for erreur in (erreurs_reseau + erreurs_format)[:30]:
                st.warning(erreur)
            if not erreurs_reseau and not erreurs_format:
                st.write("Aucune erreur signalée.")

    except Exception as erreur:
        st.error(
            "MonIA n'a pas pu récupérer les archives automatiquement."
        )
        st.write(str(erreur))
        st.markdown(
            f"[Ouvrir la page officielle {jeu}]({url})"
        )

st.divider()
st.header("🎲 Générer des grilles")

nombre_grilles = st.slider(
    "Nombre de grilles", 1, 20, 5
)

if st.button("Générer les grilles"):
    grilles = set()

    while len(grilles) < nombre_grilles:
        ns = tuple(sorted(random.sample(
            range(1, max_num + 1), nb_num
        )))
        bs = tuple(sorted(random.sample(
            range(1, max_bonus + 1), nb_bonus
        )))
        grilles.add((ns, bs))

    for i, (ns, bs) in enumerate(sorted(grilles), 1):
        st.write(
            f"**Grille {i} :** "
            + " – ".join(map(str, ns))
            + " | Bonus : "
            + " – ".join(map(str, bs))
        )

    st.caption(
        "Les grilles sont aléatoires. Les statistiques passées "
        "ne donnent aucun avantage prédictif garanti."
    )
