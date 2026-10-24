

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


import io
import zipfile
import itertools
import re
from collections import Counter

import pandas as pd
import streamlit as st
import requests

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
# Chargement des archives
# --------------------------------------------------

@st.cache_data(ttl=3600, show_spinner=False)
def telecharger_archive(url):
    """Télécharge une archive publique et renvoie son contenu."""
    reponse = requests.get(
        url,
        timeout=30,
        headers={"User-Agent": "MonIA-Nereon/1.0"}
    )
    reponse.raise_for_status()

    if not reponse.content:
        raise ValueError("Le fichier téléchargé est vide.")

    return reponse.content

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
# MOTEUR STATISTIQUE DE NEREON
# --------------------------------------------------

def analyser_frequences(valeurs):
    """Calcule les fréquences observées dans une série de numéros."""
    serie = pd.to_numeric(
        pd.Series(valeurs), errors="coerce"
    ).dropna()

    serie = serie[serie % 1 == 0].astype(int)

    if serie.empty:
        return pd.DataFrame(
            columns=["Numéro", "Occurrences", "Fréquence (%)"]
        )

    comptes = serie.value_counts().sort_values(
        ascending=False
    )

    resultat = comptes.rename_axis("Numéro").reset_index(
        name="Occurrences"
    )

    resultat["Fréquence (%)"] = (
        resultat["Occurrences"] / len(serie) * 100
    ).round(2)

    return resultat


def analyser_retards(valeurs):
    """Compte les tirages écoulés depuis la dernière apparition."""
    serie = pd.to_numeric(
        pd.Series(valeurs), errors="coerce"
    ).dropna()

    serie = serie[serie % 1 == 0].astype(int).tolist()

    if not serie:
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
                    use_container_width=True,
                )

                st.bar_chart(
                    resultat.set_index("Numéro")[["Occurrences"]]
                )
            else:
                st.info("Sélectionne les colonnes correspondantes.")

        st.warning(
            "Vérifie les colonnes choisies : MonIA ne peut pas connaître "
            "leur signification avec certitude à partir de leur contenu seul. "
            "Ces fréquences décrivent le passé et ne prédisent pas le prochain tirage."
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
# ===== Imports et dépendances (placer en début de app.py) =====
import io, zipfile, itertools, re, random, math
import numpy as np
import pandas as pd
import streamlit as st
import requests
from bs4 import BeautifulSoup
from collections import Counter
from datetime import datetime

# ===== Fonctions de récupération des archives officielles =====
def recuperer_liens_fdj(url_historique):
    """
    Récupère les URLs des fichiers ZIP d'archives depuis les pages FDJ.
    """
    try:
        headers = {"User-Agent": "Néréon/1.0 (+https://github.com/...)"} 
        res = requests.get(url_historique, headers=headers, timeout=10)
        res.raise_for_status()
    except Exception as e:
        st.error(f"Erreur récupération FDJ: {e}")
        return []
    soup = BeautifulSoup(res.text, 'html.parser')
    # Cherche les liens se terminant par .zip
    liens = [a['href'] for a in soup.find_all('a', href=True) if a['href'].endswith('.zip')]
    return liens

def telecharger_et_extraire_zip(zip_url):
    """
    Télécharge le ZIP à partir de l'URL et retourne un DataFrame pandas concaténé.
    """
    try:
        res = requests.get(zip_url, timeout=10)
        res.raise_for_status()
        z = zipfile.ZipFile(io.BytesIO(res.content))
    except Exception as e:
        st.warning(f"Impossible de télécharger ou d'ouvrir l'archive : {e}")
        return None
    df_total = pd.DataFrame()
    # Parcourir chaque fichier CSV/TXT dans l'archive
    for nom_fichier in z.namelist():
        if nom_fichier.lower().endswith(('.csv', '.txt')):
            try:
                contenu = z.read(nom_fichier)
                # Essayer plusieurs séparateurs si nécessaire
                for sep in [';', ',', '\t', '|']:
                    try:
                        df = pd.read_csv(io.StringIO(contenu.decode('utf-8', errors='ignore')),
                                         sep=sep, dtype=str, on_bad_lines='skip')
                        if df.shape[1] > 1:
                            df_total = pd.concat([df_total, df], ignore_index=True, sort=False)
                            break
                    except Exception:
                        continue
            except Exception as e:
                st.warning(f"Échec lecture de {nom_fichier}: {e}")
    return df_total

def charger_archives_officielles(jeu):
    """
    Charge et concatène les archives officielles selon le jeu choisi.
    jeu = "EuroMillions" ou "Loto".
    Renvoie un DataFrame pandas ou None.
    """
    if jeu == "EuroMillions":
        url = "https://www.fdj.fr/jeux-de-tirage/euromillions-my-million/historique"
    else:  # "Loto"
        url = "https://www.fdj.fr/jeux-de-tirage/loto/historique"
    st.info(f"Téléchargement des archives officielles pour {jeu}...")
    liens_zip = recuperer_liens_fdj(url)
    if not liens_zip:
        st.error("Aucun lien d'archive trouvé sur le site FDJ.")
        return None
    df_total = pd.DataFrame()
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
                    st.info("Cette grille est purement aléatoire, sans critère statistique particulier.")
                elif strat == "Fréquence":
                    occs = [stats_num.loc[stats_num['Numéro']==n, 'Occurrences'].values[0] for n in nums if n in stats_num['Numéro'].values]
                    st.info(f"Numéros choisis pour leur fréquence élevée (occurrences: {occs}).")
                else:
                    retard_vals = [retards.get(n, 0) for n in nums]
                    st.info(f"Numéros choisis pour leur grand retard (écarts: {retard_vals} tirages).")
