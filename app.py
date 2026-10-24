
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

import io
import re
import zipfile
from collections import Counter
from itertools import combinations
from datetime import datetime

import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup

st.set_page_config(
    page_title="MonIA | Laboratoire des tirages",
    page_icon="🎱",
    layout="wide",
)

HEADERS = {"User-Agent": "Mozilla/5.0 MonIA-Statistics"}
CONFIG = {
    "EuroMillions": {
        "page": "https://www.fdj.fr/jeux-de-tirage/euromillions-my-million/historique",
        "prefix": "euromillions",
        "max_n": 50,
        "max_b": 12,
        "bonus": ["etoile_1", "etoile_2"],
    },
    "Loto français": {
        "page": "https://www.fdj.fr/jeux-de-tirage/loto/historique",
        "prefix": "loto",
        "max_n": 49,
        "max_b": 10,
        "bonus": ["numero_chance"],
    },
}


def nom_normalise(value):
    return re.sub(r"[^a-z0-9]", "", str(value).lower()
                  .replace("é", "e").replace("è", "e")
                  .replace("ê", "e").replace("à", "a")
                  .replace("ù", "u").replace("ô", "o")
                  .replace("î", "i").replace("ç", "c"))


def trouver_colonne(df, candidats):
    noms = {nom_normalise(c): c for c in df.columns}
    for candidat in candidats:
        c = noms.get(nom_normalise(candidat))
        if c is not None:
            return c
    return None


@st.cache_data(ttl=3600, show_spinner=False)
def telecharger_archives(jeu):
    cfg = CONFIG[jeu]
    messages = []
    urls = []

    try:
        r = requests.get(cfg["page"], headers=HEADERS, timeout=25)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            texte = a.get_text(" ", strip=True).lower()
            candidat = (href + " " + texte).lower()

            if ".zip" in href.lower() and (
                cfg["prefix"] in candidat or "historique" in candidat
            ):
                if href.startswith("//"):
                    href = "https:" + href
                elif href.startswith("/"):
                    href = "https://www.fdj.fr" + href
                elif not href.startswith("http"):
                    continue
                urls.append(href)

    except Exception as e:
        messages.append(f"Page officielle inaccessible : {e}")

    # Archives directes courantes, utilisées comme solution de secours.
    if jeu == "Loto français":
        for periode in ["197605", "200810", "201703", "201902", "201911"]:
            urls.append(
                f"https://media.fdj.fr/static/csv/loto/loto_{periode}.zip"
            )
    else:
        for periode in [
            "200402", "201105", "201402",
            "201609", "201902", "202002"
        ]:
            urls.append(
                "https://media.fdj.fr/static/csv/euromillions/"
                f"euromillions_{periode}.zip"
            )

    archives = []
    vus = set()

    for url in dict.fromkeys(urls):
        if url in vus:
            continue
        vus.add(url)

        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            r.raise_for_status()

            if not r.content.startswith(b"PK"):
                continue

            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                for nom in z.namelist():
                    if nom.lower().endswith(".csv"):
                        archives.append((nom, z.read(nom)))
        except Exception as e:
            messages.append(f"Archive non récupérée ({url}) : {e}")

    return archives, messages, len(vus)


def lire_csv(contenu):
    for enc in ["utf-8-sig", "cp1252", "latin1"]:
        try:
            df = pd.read_csv(
                io.BytesIO(contenu),
                sep=";",
                encoding=enc,
                dtype=str,
                on_bad_lines="skip",
            )
            if len(df.columns) > 5:
                df.columns = [c.strip() for c in df.columns]
                return df
        except Exception:
            pass
    return None


def preparer_donnees(archives, jeu):
    cfg = CONFIG[jeu]
    tirages = []
    erreurs = []

    cols_n = [
        ["boule_1"], ["boule_2"], ["boule_3"],
        ["boule_4"], ["boule_5"]
    ]
    cols_b = cfg["bonus"]
    max_n = cfg["max_n"]
    max_b = cfg["max_b"]

    for nom, contenu in archives:
        df = lire_csv(contenu)
        if df is None:
            erreurs.append(f"{nom} : CSV illisible")
            continue

        date_col = trouver_colonne(df, ["date_de_tirage", "date_tirage", "date"])
        num_cols = [trouver_colonne(df, c) for c in cols_n]
        bonus_cols = [trouver_colonne(df, [c]) for c in cols_b]

        if any(c is None for c in num_cols + bonus_cols):
            erreurs.append(
                f"{nom} : colonnes de numéros non reconnues"
            )
            continue

        for _, row in df.iterrows():
            try:
                nums = [int(float(row[c])) for c in num_cols]
                bonus = [int(float(row[c])) for c in bonus_cols]

                if (
                    len(set(nums)) != 5
                    or any(n < 1 or n > max_n for n in nums)
                    or len(set(bonus)) != len(bonus_cols)
                    or any(b < 1 or b > max_b for b in bonus)
                ):
                    continue

                date = str(row[date_col]).strip() if date_col else ""
                date = date or "Date inconnue"

                gagnants = {}
                gains = {}
                for c in df.columns:
                    cn = nom_normalise(c)
                    if "nombredegagnant" in cn and "rang" in cn:
                        gagnants[c] = row[c]
                    if "rapportdurang" in cn:
                        gains[c] = row[c]

                tirages.append({
                    "date": date,
                    "numeros": sorted(nums),
                    "bonus": sorted(bonus),
                    "gagnants": gagnants,
                    "gains": gains,
                    "archive": nom,
                })

            except (ValueError, TypeError, KeyError):
                continue

    uniques = {}
    for t in tirages:
        cle = (t["date"], tuple(t["numeros"]), tuple(t["bonus"]))
        uniques[cle] = t

    resultats = list(uniques.values())

    def date_tri(t):
        try:
            return pd.to_datetime(
                t["date"], dayfirst=True, errors="coerce"
            )
        except Exception:
            return pd.NaT

    resultats.sort(key=lambda t: (
        pd.isna(date_tri(t)),
        date_tri(t) if not pd.isna(date_tri(t)) else pd.Timestamp.min
    ))
    return resultats, erreurs


def tableau_frequences(tirages, cle, maximum, etiquette):
    compte = Counter()
    for t in tirages:
        compte.update(t[cle])

    df = pd.DataFrame({
        etiquette: range(1, maximum + 1),
        "Sorties": [compte[n] for n in range(1, maximum + 1)]
    })
    df["Pourcentage des tirages"] = (
        df["Sorties"] / len(tirages) * 100 if tirages else 0
    )
    return df


def afficher(jeu, tirages, erreurs, archives_count, tentatives):
    st.caption(
        f"Archives lues : {archives_count} · "
        f"Tirages uniques : {len(tirages)} · "
        f"Vérification : {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    )

    if not tirages:
        st.error("Aucun tirage reconnu. Consulte les diagnostics ci-dessous.")
        st.info(
            "La structure des liens ou des colonnes peut avoir changé. "
            "MonIA n'invente aucun résultat pour remplir les graphiques."
        )
        return

    cfg = CONFIG[jeu]
    st.success(f"{len(tirages)} tirages analysés pour {jeu}.")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Vue d'ensemble", "Numéros", "Paires et triplets",
        "Gagnants et gains", "Historique"
    ])

    freq_n = tableau_frequences(
        tirages, "numeros", cfg["max_n"], "Numéro"
    )
    freq_b = tableau_frequences(
        tirages, "bonus", cfg["max_b"], "Bonus"
    )

    with tab1:
        a, b, c = st.columns(3)
        a.metric("Tirages analysés", len(tirages))
        b.metric("Numéros distincts observés", int((freq_n["Sorties"] > 0).sum()))
        c.metric("Archives lues", archives_count)
        st.subheader("Numéros les plus fréquents")
        st.bar_chart(freq_n.sort_values("Sorties", ascending=False)
                     .head(15).set_index("Numéro")["Sorties"])
        st.subheader("Fréquence des bonus")
        st.bar_chart(freq_b.set_index("Bonus")["Sorties"])
        st.caption(
            "Une fréquence élevée dans le passé ne rend pas un numéro "
            "plus probable au prochain tirage."
        )

    with tab2:
        st.subheader("Tous les numéros")
        st.dataframe(
            freq_n.sort_values("Sorties", ascending=False),
            hide_index=True, use_container_width=True
        )
        st.subheader("Écarts depuis la dernière apparition")
        derniere = {}
        for i, t in enumerate(tirages):
            for n in t["numeros"]:
                derniere[n] = i
        ecarts = pd.DataFrame([
            {
                "Numéro": n,
                "Tirages depuis dernière sortie":
                    len(tirages) - 1 - derniere[n]
                    if n in derniere else len(tirages)
            }
            for n in range(1, cfg["max_n"] + 1)
        ])
        st.dataframe(
            ecarts.sort_values(
                "Tirages depuis dernière sortie", ascending=False
            ),
            hide_index=True, use_container_width=True
        )
        st.subheader("Fréquences des bonus")
        st.dataframe(freq_b, hide_index=True, use_container_width=True)

    with tab3:
        paires = Counter()
        triplets = Counter()
        for t in tirages:
            paires.update(combinations(t["numeros"], 2))
            triplets.update(combinations(t["numeros"], 3))
        paires_df = pd.DataFrame([
            {"Paire": f"{a}-{b}", "Occurrences": n}
            for (a, b), n in paires.most_common(20)
        ])
        triplets_df = pd.DataFrame([
            {"Triplet": f"{a}-{b}-{c}", "Occurrences": n}
            for (a, b, c), n in triplets.most_common(20)
        ])
        st.subheader("20 paires les plus fréquentes")
        st.dataframe(paires_df, hide_index=True, use_container_width=True)
        st.subheader("20 triplets les plus fréquents")
        st.dataframe(triplets_df, hide_index=True, use_container_width=True)

    with tab4:
        st.write(
            "Ces tableaux utilisent les colonnes de gagnants et de rapports "
            "présentes dans les archives. Les formats historiques peuvent varier."
        )
        lignes = []
        for t in tirages:
            ligne = {"Date": t["date"]}
            for c, v in t["gagnants"].items():
                ligne[c] = v
            for c, v in t["gains"].items():
                ligne[c] = v
            if len(ligne) > 1:
                lignes.append(ligne)
        if lignes:
            df_g = pd.DataFrame(lignes)
            st.dataframe(df_g.tail(100), hide_index=True,
                         use_container_width=True)
            st.download_button(
                "Télécharger les données gagnants",
                df_g.to_csv(index=False).encode("utf-8-sig"),
                file_name="monia_gagnants.csv",
                mime="text/csv",
            )
        else:
            st.warning(
                "Aucune colonne de gagnants reconnue dans ces archives."
            )

    with tab5:
        df_h = pd.DataFrame([
            {
                "Date": t["date"],
                "Numéros": " - ".join(map(str, t["numeros"])),
                "Bonus": " - ".join(map(str, t["bonus"])),
                "Archive": t["archive"],
            }
            for t in tirages
        ])
        st.dataframe(df_h.tail(100), hide_index=True,
                     use_container_width=True)
        st.download_button(
            "Télécharger l'historique analysé",
            df_h.to_csv(index=False).encode("utf-8-sig"),
            file_name="monia_historique.csv",
            mime="text/csv",
        )


st.title("🎱 MonIA — Laboratoire statistique")
st.write(
    "Récupération des archives publiques, analyse historique et "
    "étude des gagnants pour EuroMillions et Loto français."
)
st.warning(
    "Les jeux sont aléatoires. Les statistiques historiques ne prédisent "
    "pas le prochain tirage et aucune grille ne garantit un gain."
)

jeu = st.sidebar.selectbox("Jeu à analyser", list(CONFIG))
if st.sidebar.button("🔄 Rechercher les archives à nouveau"):
    telecharger_archives.clear()

with st.spinner("Recherche et lecture des archives publiques…"):
    try:
        archives, messages, tentatives = telecharger_archives(jeu)
        tirages, erreurs = preparer_donnees(archives, jeu)
        afficher(jeu, tirages, erreurs + messages,
                 len(archives), tentatives)

        with st.expander("Diagnostics techniques"):
            st.write(f"Liens testés : {tentatives}")
            st.write(f"Fichiers CSV extraits : {len(archives)}")
            st.write(f"Tirages valides : {len(tirages)}")
            for erreur in (erreurs + messages)[:30]:
                st.write("• " + erreur)
            if not erreurs and not messages:
                st.write("Aucune erreur signalée.")

    except Exception as e:
        st.error(f"Erreur pendant l'analyse : {e}")
        st.write(
            "Vérifie les dépendances, la connexion Internet et les "
            "diagnostics de déploiement Streamlit."
        )

st.divider()
st.subheader("🎲 Générateur de grilles")
cfg = CONFIG[jeu]
nombre = st.slider("Nombre de grilles", 1, 20, 5)

if st.button("Générer des grilles"):
    for i in range(1, nombre + 1):
        ns = sorted(__import__("random").sample(
            range(1, cfg["max_n"] + 1), 5
        ))
        bs = sorted(__import__("random").sample(
            range(1, cfg["max_b"] + 1), len(cfg["bonus"])
        ))
        st.write(
            f"**Grille {i} :** {' - '.join(map(str, ns))} "
            f"| Bonus : {' - '.join(map(str, bs))}"
        )
