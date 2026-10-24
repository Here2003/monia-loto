import io
import math
import random
import re
import zipfile
import itertools
from collections import Counter

import pandas as pd
import requests
import streamlit as st

INSTRUCTIONS_NEREON = """
Tu es Néréon, le cerveau scientifique de MonIA.

MISSION
Tu analyses les archives historiques du Loto français et d’EuroMillions,
les résultats officiels, les fréquences, les retards, les paires,
les triplets, les nombres de gagnants et les montants des gains publiés.

RIGUEUR SCIENTIFIQUE
- Utilise uniquement des données réellement disponibles et vérifiées.
- Privilégie les sources officielles de la FDJ et des loteries nationales.
- Sépare les numéros principaux, les étoiles et le numéro Chance.
- Explique les calculs, les périodes étudiées et les limites des données.
- Ne fabrique jamais de résultats, de sources ou de statistiques.
- Ne prétends jamais avoir consulté Internet si tu ne l'as pas fait.
- Signale les données manquantes et les changements de règles.

GRILLES
- Analyse les données disponibles avant de proposer des grilles.
- Explique les critères statistiques utilisés.
- Compare les méthodes à une sélection aléatoire lorsque c'est possible.
- Ne présente jamais un score statistique comme une probabilité de gagner.
- Rappelle que chaque combinaison valide a la même probabilité de sortir
  lors d'un tirage équitable.

GAINS ET GAGNANTS
- Analyse uniquement les nombres de gagnants et les montants publiés.
- Distingue le gain individuel du montant total distribué.
- N'invente jamais l'identité ou les habitudes des gagnants.

RECHERCHE
- Utilise uniquement les outils réellement disponibles dans l'application.
- Vérifie les sources, les dates et les données avant de conclure.
- Respecte les conditions d'utilisation des sites consultés.

RÉPONSES
Réponds toujours en français, clairement et avec méthode :
1. Question étudiée
2. Sources et période
3. Données analysées
4. Méthode
5. Résultats
6. Limites
7. Conclusion
8. Grilles proposées si elles sont demandées

RÈGLE ABSOLUE
Sois rigoureux, transparent et reproductible.
Si tu ne sais pas, dis-le.
"""

# --------------------------------------------------
# Configuration de la page
# --------------------------------------------------

st.set_page_config(
    page_title="MonIA — Laboratoire statistique",
    page_icon="🧠",
    layout="wide",
)

st.title("🧠 Néréon")
st.subheader("Intelligence scientifique — Laboratoire MonIA")
st.caption(
    "Néréon — analyse les archives, teste les hypothèses "
    "et explique ses conclusions à partir des données."
)

# --------------------------------------------------
# Règles des jeux
# --------------------------------------------------

REGLES = {
    "EuroMillions": {
        "nb_num": 5, "max_num": 50,
        "nb_bonus": 2, "max_bonus": 12,
        "nom_bonus": "Étoiles",
    },
    "Loto": {
        "nb_num": 5, "max_num": 49,
        "nb_bonus": 1, "max_bonus": 10,
        "nom_bonus": "Numéro Chance",
    },
}

# Archives officielles FDJ (page « Historique » de chaque jeu).
ARCHIVES_FDJ = {
    "EuroMillions": [
        "https://www.sto.api.fdj.fr/anonymous/service-draw-info/v3/documentations/1a2b3c4d-9876-4562-b3fc-2c963f66afe6",
        "https://www.sto.api.fdj.fr/anonymous/service-draw-info/v3/documentations/1a2b3c4d-9876-4562-b3fc-2c963f66afd6",
        "https://www.sto.api.fdj.fr/anonymous/service-draw-info/v3/documentations/1a2b3c4d-9876-4562-b3fc-2c963f66afc6",
        "https://www.sto.api.fdj.fr/anonymous/service-draw-info/v3/documentations/1a2b3c4d-9876-4562-b3fc-2c963f66afb6",
        "https://www.sto.api.fdj.fr/anonymous/service-draw-info/v3/documentations/1a2b3c4d-9876-4562-b3fc-2c963f66afa9",
        "https://www.sto.api.fdj.fr/anonymous/service-draw-info/v3/documentations/1a2b3c4d-9876-4562-b3fc-2c963f66afa8",
    ],
    "Loto": [
        "https://www.sto.api.fdj.fr/anonymous/service-draw-info/v3/documentations/1a2b3c4d-9876-4562-b3fc-2c963f66afp6",
        "https://www.sto.api.fdj.fr/anonymous/service-draw-info/v3/documentations/1a2b3c4d-9876-4562-b3fc-2c963f66afo6",
        "https://www.sto.api.fdj.fr/anonymous/service-draw-info/v3/documentations/1a2b3c4d-9876-4562-b3fc-2c963f66afn6",
        "https://www.sto.api.fdj.fr/anonymous/service-draw-info/v3/documentations/1a2b3c4d-9876-4562-b3fc-2c963f66afm6",
        "https://www.sto.api.fdj.fr/anonymous/service-draw-info/v3/documentations/1a2b3c4d-9876-4562-b3fc-2c963f66afl6",
    ],
}

# --------------------------------------------------
# Affichage compatible avec toutes les versions de Streamlit
# --------------------------------------------------

def tableau(donnees, hide_index=False):
    try:
        st.dataframe(donnees, hide_index=hide_index, width="stretch")
    except Exception:
        st.dataframe(
            donnees, hide_index=hide_index, use_container_width=True
        )

# --------------------------------------------------
# Chargement des archives
# --------------------------------------------------

@st.cache_data(ttl=3600, show_spinner=False)
def telecharger_archive(url):
    """Télécharge une archive publique et renvoie son contenu."""
    reponse = requests.get(
        url,
        timeout=30,
        headers={"User-Agent": "MonIA-Nereon/1.0"},
    )
    reponse.raise_for_status()

    if not reponse.content:
        raise ValueError("Le fichier téléchargé est vide.")

    return reponse.content


def lire_table(nom, contenu):
    """Lit un CSV/TXT en essayant plusieurs encodages et séparateurs."""
    for encodage in ("utf-8-sig", "cp1252", "latin1"):
        try:
            texte = contenu.decode(encodage)
        except UnicodeDecodeError:
            continue

        for separateur in (";", ",", "\t", "|"):
            try:
                table = pd.read_csv(
                    io.StringIO(texte),
                    sep=separateur,
                    dtype=str,
                    on_bad_lines="skip",
                    index_col=False,
                )
            except Exception:
                continue

            if len(table.columns) > 1 and len(table) > 0:
                table.columns = [str(c).strip() for c in table.columns]
                return [(nom, table)]

    raise ValueError(f"Impossible de lire le fichier : {nom}")


@st.cache_data(show_spinner=False)
def lire_fichier(nom, contenu):
    """Lit un fichier CSV, TXT ou ZIP et renvoie une liste (nom, table)."""
    extension = nom.lower()
    fichiers = []

    if extension.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(contenu)) as archive:
            for nom_interne in archive.namelist():
                if nom_interne.lower().endswith((".csv", ".txt")):
                    fichiers.extend(
                        lire_table(nom_interne, archive.read(nom_interne))
                    )
    elif extension.endswith((".csv", ".txt")):
        fichiers = lire_table(nom, contenu)
    else:
        raise ValueError(
            "Format non pris en charge. Utilise un fichier CSV, TXT ou ZIP."
        )

    return fichiers


def charger_archives_officielles(jeu):
    """Télécharge les archives FDJ du jeu choisi. Renvoie (tables, erreurs)."""
    tables_off, erreurs_off = [], []
    for i, url in enumerate(ARCHIVES_FDJ[jeu], 1):
        nom = f"fdj_{jeu.lower()}_{i}.zip"
        try:
            contenu = telecharger_archive(url)
            tables_off.extend(lire_fichier(nom, contenu))
        except Exception as e:
            erreurs_off.append(f"{nom} : {e}")
    return tables_off, erreurs_off

# --------------------------------------------------
# Barre latérale
# --------------------------------------------------

with st.sidebar:
    st.header("📚 Sources de données")
    jeu = st.radio("Jeu étudié", ["EuroMillions", "Loto"])

    fichiers = st.file_uploader(
        "Importer les archives CSV ou ZIP",
        type=["csv", "txt", "zip"],
        accept_multiple_files=True,
        help="Les fichiers sont analysés pendant cette session.",
    )

    st.write("**ou**")
    if st.button("⬇️ Charger les archives officielles FDJ"):
        with st.spinner("Téléchargement des archives FDJ…"):
            t_off, e_off = charger_archives_officielles(jeu)
        st.session_state["tables_officielles"] = t_off
        st.session_state["erreurs_officielles"] = e_off
        st.session_state["jeu_officiel"] = jeu

    if st.session_state.get("tables_officielles"):
        st.caption(
            f"Archives FDJ chargées : {st.session_state['jeu_officiel']}."
        )
        if st.button("Retirer les archives FDJ"):
            st.session_state.pop("tables_officielles", None)
            st.session_state.pop("erreurs_officielles", None)
            st.session_state.pop("jeu_officiel", None)
            st.rerun()

    st.caption(
        "Les données importées ne sont pas enregistrées dans un "
        "historique permanent par cette application."
    )

tables = []
erreurs = list(st.session_state.get("erreurs_officielles", []))

tables.extend(st.session_state.get("tables_officielles", []))

if fichiers:
    for fichier in fichiers:
        try:
            tables.extend(lire_fichier(fichier.name, fichier.getvalue()))
        except Exception as e:
            erreurs.append(f"{fichier.name} : {e}")

for erreur in erreurs:
    st.warning(erreur)

if not tables:
    st.info(
        "Importe une ou plusieurs archives (ou charge les archives "
        "officielles FDJ dans la barre latérale) pour commencer. "
        "Les onglets et les outils d'analyse sont prêts."
    )

# --------------------------------------------------
# Moteur statistique de Néréon
# --------------------------------------------------

def valeurs_entieres(df, colonnes, maximum=None):
    """Toutes les valeurs entières (1..maximum) des colonnes, mises bout à bout."""
    if df is None or not colonnes:
        return pd.Series(dtype=int)

    valeurs = pd.concat(
        [pd.to_numeric(df[c], errors="coerce") for c in colonnes],
        ignore_index=True,
    ).dropna()
    valeurs = valeurs[valeurs % 1 == 0].astype(int)
    valeurs = valeurs[valeurs >= 1]
    if maximum is not None:
        valeurs = valeurs[valeurs <= maximum]
    return valeurs


def calculer_frequences(df, colonnes, maximum=None):
    """Fréquences observées. Renvoie un DataFrame ou None."""
    valeurs = valeurs_entieres(df, colonnes, maximum)
    if valeurs.empty:
        return None

    compte = valeurs.value_counts().sort_index()
    resultat = pd.DataFrame({
        "Numéro": compte.index,
        "Occurrences": compte.values,
        "Fréquence (%)": (compte.values / compte.sum() * 100).round(3),
    })
    return resultat.sort_values(
        ["Occurrences", "Numéro"], ascending=[False, True]
    ).reset_index(drop=True)


def calculer_retards(df, colonnes, maximum=None):
    """
    Retard de chaque numéro = nombre de tirages écoulés depuis sa dernière
    sortie (df doit être trié du plus ancien au plus récent).
    """
    if df is None or not colonnes:
        return None

    bloc = df[colonnes].apply(pd.to_numeric, errors="coerce")
    nb_tirages = len(bloc)
    if nb_tirages == 0:
        return None

    derniere_sortie = {}
    for position, ligne in enumerate(bloc.itertuples(index=False)):
        for v in ligne:
            if pd.notna(v) and float(v).is_integer() and v >= 1:
                derniere_sortie[int(v)] = position

    if not derniere_sortie:
        return None

    plafond = maximum or max(derniere_sortie)
    lignes = []
    for numero in range(1, plafond + 1):
        if numero in derniere_sortie:
            retard = nb_tirages - 1 - derniere_sortie[numero]
        else:
            retard = nb_tirages
        lignes.append({"Numéro": numero, "Retard (tirages)": retard})

    return pd.DataFrame(lignes).sort_values(
        ["Retard (tirages)", "Numéro"], ascending=[False, True]
    ).reset_index(drop=True)


def trier_chronologiquement(table):
    """Trie du plus ancien au plus récent grâce à la colonne de date."""
    candidates = [
        c for c in table.columns
        if re.search(r"date.*tirage|^date", str(c), re.IGNORECASE)
        and not re.search(r"forclusion", str(c), re.IGNORECASE)
    ]
    if not candidates:
        return table, None

    colonne = candidates[0]
    brut = table[colonne].astype(str).str.strip()

    dates = pd.to_datetime(brut, format="%d/%m/%Y", errors="coerce")
    manquantes = dates.isna()
    if manquantes.any():
        dates = dates.fillna(
            pd.to_datetime(brut.where(manquantes), format="%Y%m%d",
                           errors="coerce")
        )
    manquantes = dates.isna()
    if manquantes.any():
        dates = dates.fillna(
            pd.to_datetime(brut.where(manquantes), dayfirst=True,
                           errors="coerce")
        )

    if dates.notna().sum() == 0:
        return table, None

    table = table.assign(_date_tri=dates).sort_values(
        "_date_tri", kind="stable"
    ).drop(columns="_date_tri").reset_index(drop=True)
    return table, colonne

# --------------------------------------------------
# Préparation des données
# --------------------------------------------------

df = None
colonne_date = None

if tables:
    df = pd.concat(
        [table for _, table in tables],
        ignore_index=True,
        sort=False,
    )
    lignes_avant = len(df)
    df = df.drop_duplicates().reset_index(drop=True)
    doublons = lignes_avant - len(df)
    df, colonne_date = trier_chronologiquement(df)

    st.success(
        f"{len(tables)} table(s) lue(s) · "
        f"{len(df):,} lignes · {len(df.columns)} colonnes"
    )
    if colonne_date is None:
        st.warning(
            "Aucune colonne de date reconnue : les retards et les "
            "« tirages récents » supposent que les lignes sont déjà "
            "classées du plus ancien au plus récent."
        )

    with st.expander("Examiner les colonnes de l'archive"):
        st.write(list(df.columns))
        tableau(df.head(10))

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

regle = REGLES[jeu]

# --------------------------------------------------
# 1. Tableau de bord
# --------------------------------------------------

with onglets[0]:
    st.header("Vue générale")
    if df is not None:
        c1, c2, c3 = st.columns(3)
        c1.metric("Lignes analysées", f"{len(df):,}")
        c2.metric("Colonnes disponibles", len(df.columns))
        c3.metric("Lignes en double supprimées", doublons)

        if colonne_date:
            dates_ok = pd.to_datetime(
                df[colonne_date], dayfirst=True, errors="coerce"
            ).dropna()
            if len(dates_ok):
                st.write(
                    f"**Période couverte** : du "
                    f"{dates_ok.min():%d/%m/%Y} au {dates_ok.max():%d/%m/%Y}"
                )

        st.write("### Aperçu des données")
        tableau(df.head(20))
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
        tableau(qualite, hide_index=True)
    else:
        st.write(
            "Ce tableau affichera le volume d'archives, les périodes "
            "couvertes, la qualité des données et les indicateurs clés."
        )

# --------------------------------------------------
# 2. Fréquences des numéros et des étoiles
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

        defaut_num = [
            c for c in colonnes_numeriques
            if re.fullmatch(r"boule_?\d", str(c), re.IGNORECASE)
        ]
        defaut_bonus = [
            c for c in colonnes_numeriques
            if re.fullmatch(r"etoile_?\d|numero_?chance", str(c),
                            re.IGNORECASE)
        ]

        colonnes_num = st.multiselect(
            "Colonnes des numéros principaux",
            options=colonnes_numeriques,
            default=defaut_num,
            key="colonnes_numeros",
        )

        colonnes_bonus = st.multiselect(
            "Colonnes des étoiles / numéro Chance",
            options=[c for c in colonnes_numeriques if c not in colonnes_num],
            default=[c for c in defaut_bonus if c not in colonnes_num],
            key="colonnes_bonus",
        )

        for titre, colonnes in [
            ("Numéros principaux", colonnes_num),
            ("Étoiles / numéro Chance", colonnes_bonus),
        ]:
            st.subheader(titre)
            resultat = calculer_frequences(df, colonnes)

            if resultat is not None:
                gauche, droite = st.columns(2)
                gauche.metric(
                    "Valeurs comptées", int(resultat["Occurrences"].sum())
                )
                droite.metric("Valeurs distinctes", len(resultat))

                tableau(resultat, hide_index=True)
                st.bar_chart(resultat.set_index("Numéro")[["Occurrences"]])

                retards = calculer_retards(df, colonnes)
                if retards is not None:
                    st.write("**Retards actuels (tirages depuis la dernière sortie)**")
                    tableau(retards.head(15), hide_index=True)
            else:
                st.info("Sélectionne les colonnes correspondantes.")

        st.warning(
            "Vérifie les colonnes choisies : MonIA ne peut pas connaître "
            "leur signification avec certitude à partir de leur contenu seul. "
            "Ces fréquences décrivent le passé et ne prédisent pas le "
            "prochain tirage."
        )

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
                valeurs = pd.to_numeric(ligne, errors="coerce").dropna()
                numeros = sorted(set(
                    int(v) for v in valeurs if float(v).is_integer()
                ))
                paires.update(itertools.combinations(numeros, 2))

            if paires:
                top = pd.DataFrame([
                    {
                        "Paire": f"{paire[0]} – {paire[1]}",
                        "Occurrences ensemble": nombre,
                    }
                    for paire, nombre in paires.most_common(30)
                ])
                st.write("### Paires les plus observées dans cet échantillon")
                tableau(top, hide_index=True)
                st.caption(
                    "Ces comptages décrivent le passé. Ils ne signifient "
                    "pas que ces paires ont plus de chances au prochain "
                    "tirage."
                )
        else:
            st.info(
                "Dans l'onglet Fréquences, sélectionne au moins deux "
                "colonnes de numéros pour étudier les paires."
            )

        st.write("### Visualisation des boules")
        if choix:
            frequences = valeurs_entieres(df, choix).value_counts()
            if len(frequences):
                numeros_tries = sorted(frequences.index)
                for debut in range(0, len(numeros_tries), 10):
                    groupe = numeros_tries[debut:debut + 10]
                    cols_ui = st.columns(len(groupe))
                    for col_ui, numero in zip(cols_ui, groupe):
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
                str(c),
                re.IGNORECASE,
            )
        ]
        if colonnes_gains:
            st.write("Colonnes potentiellement liées aux gains")
            st.write(colonnes_gains)
            col_gain = st.selectbox(
                "Choisir une colonne à examiner", colonnes_gains
            )
            affichage = [col_gain]
            if colonne_date and colonne_date != col_gain:
                affichage = [colonne_date, col_gain]
            tableau(df[affichage].tail(50).iloc[::-1], hide_index=True)
            st.caption(
                "Les archives peuvent mélanger montants, nombres de "
                "gagnants et rangs. Vérifie la signification de la colonne "
                "avant d'interpréter les valeurs."
            )
        else:
            st.warning(
                "Aucune colonne de gains ou de gagnants n'a été reconnue "
                "automatiquement. Vérifie les colonnes de l'archive."
            )
        st.write("### Données brutes")
        tableau(df.head(100))
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
        st.write(
            "Pour une grille simple : 5 numéros parmi 50 et 2 étoiles "
            "parmi 12."
        )
        total_combinaisons = math.comb(50, 5) * math.comb(12, 2)
        st.metric(
            "Chance du jackpot par grille simple",
            f"1 sur {total_combinaisons:,}".replace(",", " "),
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
        total_combinaisons = math.comb(49, 5) * 10
        st.metric(
            "Chance du jackpot par grille simple",
            f"1 sur {total_combinaisons:,}".replace(",", " "),
        )
        st.caption(
            "Calcul théorique pour les règles actuelles. Les règles ont "
            "pu changer : ne l'applique pas automatiquement aux anciennes "
            "archives."
        )

    st.write("### Ce que les statistiques peuvent démontrer")
    st.markdown(
        "- Fréquences observées dans un historique donné.\n"
        "- Écarts entre fréquences observées et attendues.\n"
        "- Associations apparentes entre numéros.\n"
        "- Incertitude statistique et limites de l'échantillon.\n\n"
        "**Elles ne démontrent pas qu'un numéro en retard est dû pour "
        "sortir.**"
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
        tableau(schema, hide_index=True)

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

# --------------------------------------------------
# Générateur de grilles
# --------------------------------------------------

def tirer_depuis_pool(classement, pool_taille, nombre, maximum):
    """Tire `nombre` numéros distincts parmi les `pool_taille` premiers."""
    if classement is None or classement.empty:
        return sorted(random.sample(range(1, maximum + 1), nombre))
    pool = [
        int(n) for n in classement["Numéro"].tolist() if 1 <= int(n) <= maximum
    ][:pool_taille]
    if len(pool) < nombre:
        pool = list(range(1, maximum + 1))
    return sorted(random.sample(pool, nombre))


def generer_grille(methode, regle, stats_num, stats_bonus,
                   retards_num, retards_bonus):
    nb_num, max_num = regle["nb_num"], regle["max_num"]
    nb_bonus, max_bonus = regle["nb_bonus"], regle["max_bonus"]

    if methode == "Aléatoire":
        numeros = sorted(random.sample(range(1, max_num + 1), nb_num))
        bonus = sorted(random.sample(range(1, max_bonus + 1), nb_bonus))

    elif methode == "Équilibrée (pairs/impairs)":
        while True:
            numeros = sorted(random.sample(range(1, max_num + 1), nb_num))
            pairs = sum(n % 2 == 0 for n in numeros)
            if 2 <= pairs <= 3:
                break
        bonus = sorted(random.sample(range(1, max_bonus + 1), nb_bonus))

    elif methode == "Fréquence":
        numeros = tirer_depuis_pool(stats_num, 15, nb_num, max_num)
        bonus = tirer_depuis_pool(stats_bonus, max(nb_bonus + 3, 5),
                                  nb_bonus, max_bonus)

    else:  # Retard
        numeros = tirer_depuis_pool(retards_num, 15, nb_num, max_num)
        bonus = tirer_depuis_pool(retards_bonus, max(nb_bonus + 3, 5),
                                  nb_bonus, max_bonus)

    return numeros, bonus


with st.expander(f"🧠 Générateur de grilles {jeu}", expanded=True):
    st.write(
        "MonIA peut générer des grilles et expliquer les critères "
        "statistiques utilisés. Aucune méthode ne prédit un tirage."
    )

    nombre_grilles = st.slider(
        "Nombre de grilles à générer",
        min_value=1,
        max_value=10,
        value=3,
        key="nombre_grilles",
    )

    methode = st.selectbox(
        "Méthode de génération",
        [
            "Aléatoire",
            "Équilibrée (pairs/impairs)",
            "Fréquence",
            "Retard",
        ],
        key="methode_generation",
    )

    if st.button("🎯 Générer mes grilles", key="generer_grilles"):
        cols_num = st.session_state.get("colonnes_numeros", [])
        cols_bonus = st.session_state.get("colonnes_bonus", [])

        if methode in ("Fréquence", "Retard") and (df is None or not cols_num):
            st.error(
                "Cette méthode a besoin des archives et des colonnes de "
                "numéros (onglet Fréquences). Utilise « Aléatoire » sinon."
            )
        else:
            stats_num = calculer_frequences(
                df, cols_num, regle["max_num"]
            )
            stats_bonus = calculer_frequences(
                df, cols_bonus, regle["max_bonus"]
            )
            retards_num = calculer_retards(
                df, cols_num, regle["max_num"]
            )
            retards_bonus = calculer_retards(
                df, cols_bonus, regle["max_bonus"]
            )

            for i in range(1, nombre_grilles + 1):
                numeros, bonus = generer_grille(
                    methode, regle, stats_num, stats_bonus,
                    retards_num, retards_bonus,
                )
                st.markdown(f"### Grille {i}")
                c1, c2 = st.columns([5, 2])
                c1.write("**Numéros** : " + " · ".join(map(str, numeros)))
                c2.write(
                    f"**{regle['nom_bonus']}** : "
                    + " · ".join(map(str, bonus))
                )

                if methode == "Fréquence" and stats_num is not None:
                    occ = {
                        int(r["Numéro"]): int(r["Occurrences"])
                        for _, r in stats_num.iterrows()
                    }
                    st.caption(
                        "Numéros tirés parmi les 15 plus fréquents. "
                        "Occurrences : "
                        + ", ".join(f"{n}→{occ.get(n, 0)}" for n in numeros)
                    )
                elif methode == "Retard" and retards_num is not None:
                    ret = {
                        int(r["Numéro"]): int(r["Retard (tirages)"])
                        for _, r in retards_num.iterrows()
                    }
                    st.caption(
                        "Numéros tirés parmi les 15 plus en retard. "
                        "Retards (tirages) : "
                        + ", ".join(f"{n}→{ret.get(n, 0)}" for n in numeros)
                    )

            st.info(
                "Toutes ces grilles sont valides et ont exactement la même "
                "probabilité de sortir. Les critères (fréquence, retard, "
                "équilibre pair/impair) décrivent le passé ou la "
                "présentation : ils ne donnent aucun avantage démontré."
            )

st.caption(
    "MonIA — outil d'analyse descriptive. Les résultats dépendent de la "
    "qualité, de la couverture et du format des archives importées."
)
