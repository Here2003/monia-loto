
import io
import zipfile
import itertools
import re
from collections import Counter

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="MonIA — Laboratoire statistique",
    page_icon="🧠",
    layout="wide",
)

st.title("🧠 MonIA")
st.subheader("Laboratoire d'analyse du Loto et d'EuroMillions")
st.caption(
    "Statistiques historiques, fréquences, gains et probabilités. "
    "Les analyses passées ne prédisent pas les prochains tirages."
)

# --------------------------------------------------
# Chargement des archives
# --------------------------------------------------

@st.cache_data(show_spinner=False)
def lire_fichier(nom, contenu):
    fichiers = []
    extension = nom.lower()

    if extension.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(contenu)) as archive:
            for nom_interne in archive.namelist():
                if nom_interne.lower().endswith((".csv", ".txt")):
                    donnees = archive.read(nom_interne)
                    fichiers.extend(
                        lire_table(nom_interne, donnees)
                    )
    elif extension.endswith((".csv", ".txt")):
        fichiers = lire_table(nom, contenu)
    else:
        raise ValueError(
            "Format non pris en charge. Utilise un fichier CSV, TXT ou ZIP."
        )

    return fichiers


def lire_table(nom, contenu):
    resultats = []
    for encodage in ("utf-8-sig", "cp1252", "latin1"):
        try:
            texte = contenu.decode(encodage)
            for separateur in (";", ",", "\t", "|"):
                try:
                    df = pd.read_csv(
                        io.StringIO(texte),
                        sep=separateur,
                        dtype=str,
                        on_bad_lines="skip",
                    )
                    if len(df.columns) > 1 and len(df) > 0:
                        df.columns = [
                            str(c).strip() for c in df.columns
                        ]
                        resultats.append((nom, df))
                        return resultats
                except Exception:
                    continue
        except UnicodeDecodeError:
            continue

    raise ValueError(f"Impossible de lire le fichier : {nom}")


with st.sidebar:
    st.header("📚 Sources de données")
    jeu = st.radio(
        "Jeu étudié",
        ["EuroMillions", "Loto"],
    )
    fichiers = st.file_uploader(
        "Importer les archives CSV ou ZIP",
        type=["csv", "txt", "zip"],
        accept_multiple_files=True,
        help="Les fichiers sont analysés pendant cette session.",
    )
    st.caption(
        "Les données importées ne sont pas enregistrées dans un "
        "historique permanent par cette application."
    )

tables = []
erreurs = []

if fichiers:
    for fichier in fichiers:
        try:
            tables.extend(
                lire_fichier(fichier.name, fichier.getvalue())
            )
        except Exception as e:
            erreurs.append(f"{fichier.name} : {e}")

for erreur in erreurs:
    st.warning(erreur)

if not tables:
    st.info(
        "Importe une ou plusieurs archives pour commencer. "
        "Les onglets et les outils d'analyse sont prêts."
    )

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

with onglets[1]:
    st.header("Fréquences et récurrences")
    if df is not None:
        st.write(
            "Sélectionne uniquement les colonnes correspondant aux "
            "numéros réellement tirés, pas les dates, les gains ou les identifiants."
        )
        colonnes_numeriques = []
        for col in df.columns:
            valeurs = pd.to_numeric(df[col], errors="coerce")
            if valeurs.notna().sum() > 0:
                colonnes_numeriques.append(col)

        suggestions = [
            c for c in colonnes_numeriques
            if re.search(
                r"boule|numero|numéro|chance|étoile|etoile|number|ball",
                c,
                re.IGNORECASE,
            )
        ]

        choix = st.multiselect(
            "Colonnes des numéros tirés",
            options=colonnes_numeriques,
            default=suggestions,
            key="colonnes_numeros",
        )

        if choix:
            serie = pd.concat(
                [
                    pd.to_numeric(df[c], errors="coerce")
                    for c in choix
                ],
                ignore_index=True,
            ).dropna()
            serie = serie[serie % 1 == 0].astype(int)
            frequences = serie.value_counts().sort_index()
            total = int(frequences.sum())

            if total:
                stats = pd.DataFrame({
                    "Numéro": frequences.index,
                    "Occurrences": frequences.values,
                    "Fréquence (%)": (
                        frequences.values / total * 100
                    ).round(3),
                }).sort_values(
                    ["Occurrences", "Numéro"],
                    ascending=[False, True],
                )

                a, b = st.columns(2)
                a.metric("Valeurs numériques comptées", f"{total:,}")
                b.metric("Numéros distincts", len(frequences))

                st.write("### Classement des numéros")
                st.dataframe(
                    stats,
                    hide_index=True,
                    use_container_width=True,
                )
                st.write("### Graphique des occurrences")
                st.bar_chart(
                    stats.set_index("Numéro")[["Occurrences"]]
                )

                st.caption(
                    "Attention : les étoiles EuroMillions et les numéros "
                    "principaux appartiennent à des ensembles différents. "
                    "Analyse-les séparément pour éviter de fausser les fréquences."
                )
        else:
            st.warning(
                "Choisis les colonnes des numéros pour calculer les fréquences."
            )
    else:
        st.write("Importe une archive pour calculer les fréquences.")

# --------------------------------------------------
# 3. Combinaisons et boules
# --------------------------------------------------

with onglets[2]:
    st.header("Combinaisons et numéros visuels")
    if df is not None:
        choix = st.session_state.get("colonnes_numeros", [])
        if len(choix) >= 2:
            nb_paires = st.slider(
                "Nombre de tirages récents à examiner",
                min_value=10,
                max_value=500,
                value=min(100, max(10, len(df))),
                key="nb_tirages_paires",
            )
            recent = df[choix].tail(nb_paires)
            paires = Counter()
            for _, ligne in recent.iterrows():
                valeurs = pd.to_numeric(
                    ligne, errors="coerce"
                ).dropna()
                numeros = sorted(set(
                    int(v) for v in valeurs
                    if float(v).is_integer()
                ))
                paires.update(itertools.combinations(numeros, 2))

            if paires:
                top = pd.DataFrame(
                    [
                        {
                            "Paire": f"{paire[0]} – {paire[1]}",
                            "Occurrences ensemble": nombre,
                        }
                        for paire, nombre in paires.most_common(30)
                    ]
                )
                st.write("### Paires les plus observées dans cet échantillon")
                st.dataframe(top, hide_index=True, use_container_width=True)
                st.caption(
                    "Ces comptages décrivent le passé. Ils ne signifient "
                    "pas que ces paires ont plus de chances au prochain tirage."
                )
        else:
            st.info(
                "Dans l'onglet Fréquences, sélectionne au moins deux "
                "colonnes de numéros pour étudier les paires."
            )

        st.write("### Visualisation des boules")
        if choix:
            valeurs = pd.concat(
                [pd.to_numeric(df[c], errors="coerce") for c in choix],
                ignore_index=True,
            ).dropna()
            valeurs = valeurs[
                (valeurs % 1 == 0) & (valeurs > 0)
            ].astype(int)
            frequences = valeurs.value_counts()
            if len(frequences):
                maximum = int(frequences.max())
                for debut in range(0, len(frequences), 10):
                    groupe = sorted(frequences.index)[debut:debut + 10]
                    colonnes = st.columns(len(groupe))
                    for col_ui, numero in zip(colonnes, groupe):
                        col_ui.markdown(
                            f"<div style='border:2px solid #8095ad;"
                            f"border-radius:50%;width:42px;height:42px;"
                            f"display:flex;align-items:center;"
                            f"justify-content:center;font-weight:bold;"
                            f"margin:auto'>{numero}</div>",
                            unsafe_allow_html=True,
                        )
                        col_ui.caption(f"{frequences[numero]} fois")
    else:
        st.write("Importe les archives pour afficher les combinaisons.")

# --------------------------------------------------
# 4. Gains et gagnants
# --------------------------------------------------

with onglets[3]:
    st.header("Analyse des gains et des gagnants")
    if df is not None:
        colonnes_gains = [
            c for c in df.columns
            if re.search(
                r"gain|rapport|jackpot|lot|gagnant|winner|prize|rang",
                c,
                re.IGNORECASE,
            )
        ]
        if colonnes_gains:
            st.write("Colonnes potentiellement liées aux gains")
            st.write(colonnes_gains)
            col_gain = st.selectbox(
                "Choisir une colonne à examiner",
                colonnes_gains,
            )
            st.dataframe(
                df[[col_gain]].head(50),
                hide_index=True,
                use_container_width=True,
            )
            st.caption(
                "Les archives peuvent mélanger montants, nombres de gagnants "
                "et rangs. Vérifie la signification de la colonne avant "
                "d'interpréter les valeurs."
            )
        else:
            st.warning(
                "Aucune colonne de gains ou de gagnants n'a été reconnue "
                "automatiquement. Vérifie les colonnes de l'archive."
            )
        st.write("### Données brutes")
        st.dataframe(df.head(100), use_container_width=True)
    else:
        st.write(
            "Cette section servira à étudier les rangs de gains, les "
            "gagnants déclarés et les montants publiés."
        )

# --------------------------------------------------
# 5. Probabilités
# --------------------------------------------------

with onglets[4]:
    st.header("Probabilités mathématiques")
    if jeu == "EuroMillions":
        st.write("Pour une grille simple : 5 numéros parmi 50 et 2 étoiles parmi 12.")
        total_combinaisons = 2_118_760 * 66
        st.metric(
            "Chance du jackpot par grille simple",
            f"1 sur {total_combinaisons:,}",
        )
        st.caption(
            "Calcul théorique : C(50,5) × C(12,2). "
            "Il suppose une grille simple valide."
        )
    else:
        st.write(
            "Pour le Loto français actuel : 5 numéros parmi 49 "
            "et 1 numéro Chance parmi 10."
        )
        import math
        total_combinaisons = math.comb(49, 5) * 10
        st.metric(
            "Chance du jackpot par grille simple",
            f"1 sur {total_combinaisons:,}",
        )
        st.caption(
            "Calcul théorique pour les règles actuelles. Les règles ont "
            "pu changer : ne l'applique pas automatiquement aux anciennes archives."
        )

    st.write("### Ce que les statistiques peuvent démontrer")
    st.markdown(
        "- Fréquences observées dans un historique donné.\n"
        "- Écarts entre fréquences observées et attendues.\n"
        "- Associations apparentes entre numéros.\n"
        "- Incertitude statistique et limites de l'échantillon.\n\n"
        "**Elles ne démontrent pas qu'un numéro en retard est dû pour sortir.**"
    )

# --------------------------------------------------
# 6. Archives
# --------------------------------------------------

with onglets[5]:
    st.header("Explorateur des archives")
    if df is not None:
        st.write("### Schéma détecté")
        schema = pd.DataFrame({
            "Colonne": df.columns,
            "Type détecté": [str(t) for t in df.dtypes],
            "Valeurs présentes": [
                int(df[c].notna().sum()) for c in df.columns
            ],
            "Valeurs manquantes": [
                int(df[c].isna().sum()) for c in df.columns
            ],
        })
        st.dataframe(schema, hide_index=True, use_container_width=True)

        st.write("### Télécharger les données combinées")
        csv = df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "Télécharger le tableau CSV combiné",
            data=csv,
            file_name="monia_donnees_combinees.csv",
            mime="text/csv",
        )
    else:
        st.write(
            "L'explorateur affichera les colonnes, les valeurs manquantes, "
            "les doublons et les fichiers chargés."
        )

st.divider()
st.caption(
    "MonIA — outil d'analyse descriptive. Les résultats dépendent de la "
    "qualité, de la couverture et du format des archives importées."
)

# --------------------------------------------------
# GENERATEUR DE GRILLES EUROMILLIONS
# --------------------------------------------------

import random

with st.expander("🧠 Générateur de grilles EuroMillions", expanded=True):
    st.write(
        "MonIA peut générer des grilles et expliquer les critères "
        "statistiques utilisés. Aucune méthode ne prédit un tirage."
    )

    nombre_grilles = st.slider(
        "Nombre de grilles à générer",
        min_value=1,
        max_value=10,
        value=3,
        key="nombre_grilles_euromillions",
    )

    methode = st.selectbox(
        "Méthode de génération",
        [
            "Aléatoire",
            "Équilibrée (pairs/impairs)",
        ],
        key="methode_generation_euromillions",
    )

    if st.button("🎯 Générer mes grilles", key="generer_grilles_euromillions"):
        grilles = []
        for _ in range(nombre_grilles):
            if methode == "Aléatoire":
                numeros = sorted(random.sample(range(1, 51), 5))
                etoiles = sorted(random.sample(range(1, 13), 2))
            else:
                numeros = []
                while len(numeros) < 5:
                    proposition = sorted(random.sample(range(1, 51), 5))
                    pairs = sum(n % 2 == 0 for n in proposition)
                    if 2 <= pairs <= 3:
                        numeros = proposition
                etoiles = sorted(random.sample(range(1, 13), 2))

            grilles.append((numeros, etoiles))

        for i, (numeros, etoiles) in enumerate(grilles, 1):
            st.markdown(f"### Grille {i}")
            c1, c2 = st.columns([5, 2])
            c1.write("**Numéros** : " + " · ".join(map(str, numeros)))
            c2.write("**Étoiles** : " + " · ".join(map(str, etoiles)))

        st.info(
            "Les deux méthodes produisent des grilles valides. "
            "L'équilibre pair/impair est un critère de présentation, "
            "pas un avantage démontré pour gagner."
        )
