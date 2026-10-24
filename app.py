
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



@st.cache_data(ttl=3600, show_spinner=False)
def telecharger_archives(jeu):
    cfg = CONFIG[jeu]
    messages = []
    archives = []
    vus = set()

    try:
        page = requests.get(
            cfg["page"],
            headers=HEADERS,
            timeout=30,
        )
        page.raise_for_status()
        soup = BeautifulSoup(page.text, "html.parser")

        # La FDJ publie des liens avec un identifiant de document.
        # On récupère les véritables URL, sans fabriquer de ZIP.
        liens = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            texte = a.get_text(" ", strip=True).lower()
            contexte = (href + " " + texte).lower()

            if "sto.api.fdj.fr" in href.lower():
                if "documentations/" in href.lower():
                    liens.append(href)
            elif ".zip" in href.lower():
                if href.startswith("/"):
                    href = "https://www.fdj.fr" + href
                if href.startswith("https://"):
                    liens.append(href)

        if not liens:
            messages.append(
                "Aucun lien d'archive détecté sur la page FDJ."
            )

        for url in dict.fromkeys(liens):
            if url in vus:
                continue
            vus.add(url)

            try:
                r = requests.get(
                    url,
                    headers=HEADERS,
                    timeout=45,
                )
                r.raise_for_status()

                if not zipfile.is_zipfile(io.BytesIO(r.content)):
                    messages.append(
                        f"Le document reçu n'est pas un ZIP : {url}"
                    )
                    continue

                with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                    for nom in z.namelist():
                        if nom.lower().endswith((".csv", ".txt")):
                            archives.append((nom, z.read(nom)))

            except Exception as e:
                messages.append(f"Échec du téléchargement {url} : {e}")

    except Exception as e:
        messages.append(f"Impossible de lire la page FDJ : {e}")

    return archives, messages, len(vus)



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
