
import io
import itertools
import math
import zipfile
from collections import Counter

import pandas as pd
import streamlit as st
import requests

st.set_page_config(
    page_title="MonIA — Néréon",
    page_icon="🧠",
    layout="wide",
)

INSTRUCTIONS_NEREON = """
Tu es Néréon, le moteur scientifique de MonIA.
Analyse uniquement les données réellement chargées ou récupérées.
Sépare observations, calculs, hypothèses et limites.
Ne prétends jamais avoir consulté une source sans l'avoir fait.
Ne confonds pas numéros principaux, étoiles et numéro Chance.
Les fréquences passées ne prédisent pas les prochains tirages équitables.
Explique les méthodes, la période et les limites.
N'invente jamais de gagnants, gains, résultats ou sources.
"""

URLS_FDJ = {
    "EuroMillions": "https://www.fdj.fr/jeux-de-tirage/euromillions-my-million/historique",
    "Loto": "https://www.fdj.fr/jeux-de-tirage/loto/historique",
}


def lire_table(nom, contenu):
    """Lit les fichiers CSV et TXT avec plusieurs encodages."""
    for encodage in ("utf-8-sig", "cp1252", "latin1"):
        try:
            texte = contenu.decode(encodage)
        except UnicodeDecodeError:
            continue

        for sep in (";", ",", "\t", "|"):
            try:
                frame = pd.read_csv(
                    io.StringIO(texte),
                    sep=sep,
                    dtype=str,
                    on_bad_lines="skip",
                )
                if len(frame.columns) > 1 and not frame.empty:
                    frame.columns = [
                        str(c).strip() for c in frame.columns
                    ]
                    return frame
            except Exception:
                continue

    raise ValueError(
        f"Impossible de lire {nom} comme CSV/TXT."
    )


def lire_fichier(nom, contenu):
    nom_bas = nom.lower()

    if nom_bas.endswith(".zip"):
        frames = []
        with zipfile.ZipFile(io.BytesIO(contenu)) as archive:
            for interne in archive.namelist():
                if interne.lower().endswith((".csv", ".txt")):
                    try:
                        frames.append(
                            lire_table(
                                interne,
                                archive.read(interne),
                            )
                        )
                    except Exception:
                        continue

        if not frames:
            raise ValueError(
                "Aucun fichier CSV/TXT lisible dans cette archive ZIP."
            )
        return frames

    if nom_bas.endswith((".csv", ".txt")):
        return [lire_table(nom, contenu)]

    raise ValueError(
        "Format non pris en charge. Utilise CSV, TXT ou ZIP."
    )


def nom_normalise(nom):
    texte = str(nom).lower().strip()
    remplacements = {
        "é": "e", "è": "e", "ê": "e", "ë": "e",
        "à": "a", "â": "a", "î": "i", "ï": "i",
        "ô": "o", "ù": "u", "û": "u", "ç": "c",
        "_": " ", "-": " ",
    }

    for a, b in remplacements.items():
        texte = texte.replace(a, b)

    return " ".join(texte.split())


def detecter_colonnes(frame):
    """Détection indicative des colonnes numériques."""
    numeriques = []

    for col in frame.columns:
        vals = pd.to_numeric(frame[col], errors="coerce")
        if vals.notna().sum() > 0:
            numeriques.append(col)

    mots_exclus = (
        "date", "gain", "jackpot", "rapport", "rang",
        "gagnant", "winner", "prize", "montant",
        "annee", "heure", "tirage id", "identifiant",
        "my million",
    )

    mots_bonus = (
        "etoile", "star", "bonus", "chance",
        "complementaire",
    )

    bonus = [
        c for c in numeriques
        if any(m in nom_normalise(c) for m in mots_bonus)
    ]

    candidats = [
        c for c in numeriques
        if c not in bonus
        and not any(
            m in nom_normalise(c) for m in mots_exclus
        )
    ]

    explicites = [
        c for c in candidats
        if any(
            m in nom_normalise(c)
            for m in ("numero", "boule", "number", "num ")
        )
    ]

    principaux = (
        explicites if len(explicites) >= 3 else candidats
    )

    return principaux, bonus, numeriques


def convertir_numeros(frame, colonnes):
    if not colonnes:
        return pd.DataFrame()

    resultat = frame[colonnes].apply(
        pd.to_numeric, errors="coerce"
    )

    resultat = resultat.where(
        resultat.notna() & (resultat % 1 == 0)
    )

    return resultat


def calculer_frequences(
    frame, colonnes, minimum=1, maximum=99
):
    donnees = convertir_numeros(frame, colonnes)

    if donnees.empty:
        return pd.DataFrame(
            columns=[
                "Numéro", "Occurrences", "Fréquence (%)"
            ]
        )

    valeurs = donnees.stack().astype(int)
    valeurs = valeurs[
        (valeurs >= minimum) & (valeurs <= maximum)
    ]

    if valeurs.empty:
        return pd.DataFrame(
            columns=[
                "Numéro", "Occurrences", "Fréquence (%)"
            ]
        )

    comptes = valeurs.value_counts().sort_values(
        ascending=False
    )

    result = comptes.rename_axis(
        "Numéro"
    ).reset_index(name="Occurrences")

    result["Fréquence (%)"] = (
        result["Occurrences"] / len(valeurs) * 100
    ).round(3)

    return result


def calculer_retards_par_tirage(
    frame, colonnes, minimum=1, maximum=99
):
    """Calcule le nombre de tirages depuis la dernière apparition."""
    donnees = convertir_numeros(frame, colonnes)

    if donnees.empty:
        return pd.DataFrame(
            columns=["Numéro", "Retard (tirages)"]
        )

    retards = []

    for numero in range(minimum, maximum + 1):
        retard = 0
        trouve = False

        for _, ligne in donnees.iloc[::-1].iterrows():
            valeurs = ligne.dropna().astype(int).tolist()

            if numero in valeurs:
                trouve = True
                break

            retard += 1

        if trouve:
            retards.append({
                "Numéro": numero,
                "Retard (tirages)": retard,
            })

    return pd.DataFrame(retards).sort_values(
        "Retard (tirages)", ascending=False
    ).reset_index(drop=True)


def calculer_paires(frame, colonnes, limite=20):
    donnees = convertir_numeros(frame, colonnes)
    compte = Counter()

    for _, ligne in donnees.iterrows():
        nums = sorted(
            set(ligne.dropna().astype(int).tolist())
        )
        compte.update(itertools.combinations(nums, 2))

    return pd.DataFrame([
        {
            "Paire": f"{a} – {b}",
            "Occurrences ensemble": n,
        }
        for (a, b), n in compte.most_common(limite)
    ])


def verifier_lignes(frame, colonnes, nombre_attendu):
    donnees = convertir_numeros(frame, colonnes)
    rapports = []

    for idx, ligne in donnees.iterrows():
        nums = ligne.dropna().astype(int).tolist()

        if len(nums) != nombre_attendu:
            rapports.append((
                idx,
                "Nombre de valeurs différent du nombre attendu",
            ))
        elif len(nums) != len(set(nums)):
            rapports.append((
                idx,
                "Numéro répété dans le même tirage",
            ))

    return rapports


def charger_page_fdj(url):
    """Vérifie l'accès à une page officielle FDJ."""
    reponse = requests.get(
        url,
        timeout=20,
        headers={
            "User-Agent": "MonIA-Nereon/1.0 "
            "(analyse statistique publique)"
        },
    )
    reponse.raise_for_status()
    return reponse.url, reponse.status_code, reponse.text[:5000]

st.title("🧠 Néréon")
st.subheader("Le laboratoire scientifique de MonIA")
st.caption(
    "Analyses reproductibles des archives importées. "
    "Les statistiques historiques ne prédisent pas les tirages futurs."
)

with st.sidebar:
    st.header("📚 Sources de données")
    jeu = st.radio("Jeu étudié", ["EuroMillions", "Loto"])
    fichiers = st.file_uploader(
        "Importer des archives CSV, TXT ou ZIP",
        type=["csv", "txt", "zip"],
        accept_multiple_files=True,
    )
    st.caption("Les fichiers importés ne sont pas enregistrés durablement.")

tables, erreurs = [], []

if fichiers:
    for fichier in fichiers:
        try:
            for frame in lire_fichier(
                fichier.name, fichier.getvalue()
            ):
                frame["_fichier_source"] = fichier.name
                tables.append(frame)
        except Exception as exc:
            erreurs.append(f"{fichier.name} : {exc}")

for erreur in erreurs:
    st.warning(erreur)

df = None
if tables:
    df = pd.concat(tables, ignore_index=True, sort=False)
    nb_avant = len(df)
    df = df.drop_duplicates().reset_index(drop=True)
    doublons_supprimes = nb_avant - len(df)
else:
    doublons_supprimes = 0

onglets = st.tabs([
    "🏠 Tableau de bord",
    "🔢 Fréquences",
    "🔗 Combinaisons",
    "💰 Gains et gagnants",
    "🎯 Probabilités",
    "📂 Archives",
])

with onglets[0]:
    st.header("Vue générale")
    if df is None:
        st.info("Importe une archive dans la barre latérale pour commencer.")
    else:
        a, b, c = st.columns(3)
        a.metric("Lignes analysées", f"{len(df):,}")
        b.metric("Colonnes", len(df.columns))
        c.metric("Doublons retirés", doublons_supprimes)
        st.write("### Aperçu")
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
        st.dataframe(
            qualite, hide_index=True, use_container_width=True
        )

with onglets[1]:
    st.header("Fréquences et retards")
    if df is None:
        st.info("Importe une archive pour commencer.")
    else:
        detect_principaux, detect_bonus, numeriques = (
            detecter_colonnes(df)
        )
        st.caption(
            "La détection est indicative. Vérifie les colonnes."
        )
        colonnes_num = st.multiselect(
            "Colonnes des numéros principaux",
            numeriques,
            default=[
                c for c in detect_principaux if c in numeriques
            ],
            key="colonnes_numeros",
        )
        colonnes_bonus = st.multiselect(
            "Colonnes des étoiles / numéro Chance",
            [c for c in numeriques if c not in colonnes_num],
            default=[
                c for c in detect_bonus if c not in colonnes_num
            ],
            key="colonnes_bonus",
        )
        limite_num = 50 if jeu == "EuroMillions" else 49

        if colonnes_num:
            stats = calculer_frequences(
                df, colonnes_num, 1, limite_num
            )
            st.subheader("Numéros principaux")
            st.dataframe(
                stats, hide_index=True, use_container_width=True
            )
            if not stats.empty:
                st.bar_chart(
                    stats.set_index("Numéro")[["Occurrences"]]
                )

            retards = calculer_retards_par_tirage(
                df, colonnes_num, 1, limite_num
            )
            st.subheader("Retards mesurés par tirage")
            st.caption(
                "Suppose que la dernière ligne est le tirage "
                "le plus récent. Vérifie l'ordre chronologique."
            )
            st.dataframe(
                retards, hide_index=True, use_container_width=True
            )

        if colonnes_bonus:
            st.subheader("Étoiles / numéro Chance")
            max_bonus = 12 if jeu == "EuroMillions" else 10
            stats_bonus = calculer_frequences(
                df, colonnes_bonus, 1, max_bonus
            )
            st.dataframe(
                stats_bonus, hide_index=True,
                use_container_width=True
            )
            if not stats_bonus.empty:
                st.bar_chart(
                    stats_bonus.set_index("Numéro")[["Occurrences"]]
                )

        if not colonnes_num and not colonnes_bonus:
            st.warning("Aucune colonne numérique sélectionnée.")

with onglets[2]:
    st.header("Paires et combinaisons")
    if df is None:
        st.info("Importe une archive pour commencer.")
    else:
        cols = st.session_state.get("colonnes_numeros", [])
        if len(cols) < 2:
            st.info(
                "Choisis les colonnes des numéros principaux "
                "dans l'onglet Fréquences."
            )
        else:
            n_recent = st.slider(
                "Nombre de lignes à examiner (fin du fichier)",
                min_value=1,
                max_value=max(1, min(1000, len(df))),
                value=min(100, len(df)),
            )
            paires = calculer_paires(df.tail(n_recent), cols)
            st.dataframe(
                paires, hide_index=True, use_container_width=True
            )
            st.caption(
                "Les paires observées ne prédisent pas le prochain tirage."
            )

with onglets[3]:
    st.header("Gains et gagnants publiés")
    if df is None:
        st.info(
            "Importe une archive contenant des données de gains "
            "ou de gagnants."
        )
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
            st.dataframe(
                df[candidats].head(100),
                use_container_width=True,
            )
            st.warning(
                "Vérifie les intitulés et les unités : "
                "gagnants, gain individuel et montant total "
                "sont différents."
            )
        else:
            st.info(
                "Aucune colonne de gains/gagnants détectée "
                "dans les fichiers importés."
            )

with onglets[4]:
    st.header("Probabilités théoriques")
    if jeu == "EuroMillions":
        total = math.comb(50, 5) * math.comb(12, 2)
        st.write(
            "Grille simple : 5 numéros parmi 50 et "
            "2 étoiles parmi 12."
        )
    else:
        total = math.comb(49, 5) * 10
        st.write(
            "Grille simple du Loto actuel : 5 numéros "
            "parmi 49 et 1 numéro Chance parmi 10."
        )

    st.metric("Probabilité théorique du jackpot", f"1 sur {total:,}")
    st.caption(
        "Ces règles ne s'appliquent pas nécessairement "
        "à toutes les périodes historiques."
    )
    st.markdown(
        "**À retenir :** dans un tirage équitable, chaque "
        "combinaison valide a la même probabilité. "
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
            "Valeurs présentes": [
                int(df[c].notna().sum()) for c in df.columns
            ],
            "Valeurs manquantes": [
                int(df[c].isna().sum()) for c in df.columns
            ],
        })
        st.dataframe(
            schema, hide_index=True, use_container_width=True
        )
        st.download_button(
            "Télécharger les données combinées (CSV)",
            data=df.to_csv(index=False).encode("utf-8-sig"),
            file_name="monia_donnees_combinees.csv",
            mime="text/csv",
        )

    st.divider()
    st.write("### Vérifier l'accès aux pages officielles")
    st.caption(
        "Ce test vérifie l'accès à la page FDJ, "
        "mais ne télécharge pas automatiquement les archives."
    )
    if st.button("Tester la page officielle FDJ"):
        with st.spinner("Vérification de l'accès à la page officielle…"):
            try:
                url_finale, statut, _ = charger_page_fdj(
                    URLS_FDJ[jeu]
                )
                st.success(
                    f"Page accessible (HTTP {statut}) : {url_finale}"
                )
                st.info(
                    "L'extraction automatique des liens d'archives "
                    "reste à développer et à valider."
                )
            except Exception as exc:
                st.error(
                    f"Page non accessible depuis l'application : {exc}"
                )

st.divider()
st.header("🧠 Néréon — analyse autonome")

if df is None:
    st.info(
        "Importe une archive pour que Néréon analyse "
        "des données réelles."
    )
else:
    if st.button(
        "🔬 Analyser automatiquement les données",
        type="primary",
    ):
        colonnes_num = st.session_state.get(
            "colonnes_numeros", []
        )
        colonnes_bonus = st.session_state.get(
            "colonnes_bonus", []
        )

        if not colonnes_num:
            st.warning(
                "Ouvre d'abord l'onglet Fréquences et vérifie "
                "les colonnes des numéros principaux."
            )
        else:
            with st.spinner(
                "Contrôle des données et calcul des statistiques…"
            ):
                maximum = 50 if jeu == "EuroMillions" else 49
                stats = calculer_frequences(
                    df, colonnes_num, 1, maximum
                )
                paires = calculer_paires(
                    df, colonnes_num, 10
                )
                retards = calculer_retards_par_tirage(
                    df, colonnes_num, 1, maximum
                )
                invalides = verifier_lignes(
                    df, colonnes_num, 5
                )

            st.subheader("1. Résumé des données")
            st.write(f"Jeu sélectionné : **{jeu}**")
            st.write(f"Lignes disponibles : **{len(df)}**")
            st.write(
                "Colonnes principales analysées : "
                f"**{', '.join(colonnes_num)}**"
            )
            st.write(
                "Lignes présentant une anomalie de nombre "
                "de numéros ou un doublon interne : "
                f"**{len(invalides)}**"
            )

            st.subheader("2. Fréquences principales")
            st.dataframe(
                stats, hide_index=True, use_container_width=True
            )

            st.subheader("3. Paires les plus observées")
            st.dataframe(
                paires, hide_index=True, use_container_width=True
            )

            st.subheader("4. Retards observés")
            st.dataframe(
                retards, hide_index=True, use_container_width=True
            )

            if colonnes_bonus:
                st.subheader("5. Fréquences bonus séparées")
                stats_bonus = calculer_frequences(
                    df,
                    colonnes_bonus,
                    1,
                    12 if jeu == "EuroMillions" else 10,
                )
                st.dataframe(
                    stats_bonus,
                    hide_index=True,
                    use_container_width=True,
                )

            st.subheader("Conclusion de Néréon")
            st.write(
                "Cette analyse décrit les archives chargées. "
                "Les résultats dépendent du choix des colonnes, "
                "de la période et de l'ordre des lignes. "
                "Les fréquences, retards et paires ne prouvent pas "
                "qu'une combinaison sera plus susceptible de sortir "
                "au prochain tirage."
            )

            if invalides:
                st.warning(
                    "Certaines lignes doivent être vérifiées. "
                    "Les règles et formats peuvent varier selon "
                    "la période."
                )
            else:
                st.success(
                    "Aucune anomalie simple de nombre de numéros "
                    "ou de répétition interne détectée."
                )

st.caption(
    "MonIA — Néréon | Analyses descriptives reproductibles. "
    "Les sources externes ne sont considérées comme consultées "
    "qu'après un accès effectif."
)

# ============================================================
# GENERATEUR DE GRILLES NEREON
# Frequences historiques + retards + equilibre
# ============================================================

import random


def generer_grille_nereon(
    frame,
    colonnes,
    jeu_selectionne,
    mode="mixte",
    utiliser_bonus=True,
    colonnes_bonus=None,
):
    """Genere une grille a partir des archives chargees.

    Les scores servent a classer les numeros historiques.
    Ils ne constituent pas une prediction des prochains tirages.
    """
    if frame is None or frame.empty:
        raise ValueError("Aucune archive n'est chargee.")

    if len(colonnes) != 5:
        raise ValueError(
            "Selectionne exactement 5 colonnes de numeros principaux."
        )

    if jeu_selectionne == "EuroMillions":
        max_numero = 50
        max_bonus = 12
        nb_bonus = 2
    else:
        max_numero = 49
        max_bonus = 10
        nb_bonus = 1

    donnees = convertir_numeros(frame, colonnes)

    if donnees.empty:
        raise ValueError("Les colonnes selectionnees sont vides.")

    # Garder les lignes contenant exactement cinq numeros valides.
    lignes = []
    for _, ligne in donnees.iterrows():
        valeurs = ligne.dropna().astype(int).tolist()
        if (
            len(valeurs) == 5
            and len(set(valeurs)) == 5
            and all(1 <= n <= max_numero for n in valeurs)
        ):
            lignes.append(valeurs)

    if len(lignes) < 10:
        raise ValueError(
            "Il faut au moins 10 tirages valides pour une analyse "
            "historique indicative. Verifie les colonnes et les archives."
        )

    total = len(lignes)
    comptes = Counter(n for tirage in lignes for n in tirage)
    frequences = {
        n: comptes.get(n, 0) / total
        for n in range(1, max_numero + 1)
    }

    # Retard actuel : nombre de tirages depuis la derniere sortie.
    retards = {}
    for n in range(1, max_numero + 1):
        retard = 0
        for tirage in reversed(lignes):
            if n in tirage:
                break
            retard += 1
        retards[n] = retard

    freq_max = max(frequences.values()) or 1
    retard_max = max(retards.values()) or 1

    scores = {}
    for n in range(1, max_numero + 1):
        f = frequences[n] / freq_max
        r = retards[n] / retard_max

        if mode == "frequences":
            score = f
        elif mode == "retards":
            score = r
        else:
            # Priorite aux frequences, avec une contribution moderee
            # des retards. Cela ne change pas la probabilite reelle.
            score = 0.65 * f + 0.35 * r

        scores[n] = max(score, 0.01)

    # Pondération des choix sans remise.
    def choisir_pondere(candidats, poids):
        candidats = list(candidats)
        poids = [max(float(poids[n]), 0.001) for n in candidats]
        return random.choices(candidats, weights=poids, k=1)[0]

    def construire_numeros():
        choisis = []

        for _ in range(5):
            disponibles = [n for n in scores if n not in choisis]

            # Equilibre souple entre petits/grands et pairs/impairs.
            def poids_equilibre(n):
                poids = scores[n]

                if len(choisis) >= 2:
                    nb_pairs = sum(x % 2 == 0 for x in choisis)
                    nb_impairs = len(choisis) - nb_pairs

                    if n % 2 == 0 and nb_pairs >= 3:
                        poids *= 0.55
                    if n % 2 == 1 and nb_impairs >= 3:
                        poids *= 0.55

                    nb_bas = sum(x <= max_numero // 2 for x in choisis)
                    nb_hauts = len(choisis) - nb_bas

                    if n <= max_numero // 2 and nb_bas >= 3:
                        poids *= 0.60
                    if n > max_numero // 2 and nb_hauts >= 3:
                        poids *= 0.60

                return poids

            poids = {n: poids_equilibre(n) for n in disponibles}
            choisis.append(choisir_pondere(disponibles, poids))

        return sorted(choisis)

    def construire_bonus():
        if not utiliser_bonus:
            return []

        bonus_cols = colonnes_bonus or []
        bonus_cols = [
            c for c in bonus_cols
            if c in frame.columns and c not in colonnes
        ]

        # Si les colonnes bonus n'ont pas ete selectionnees,
        # tirage aleatoire uniforme plutot que fausse analyse.
        if not bonus_cols:
            return sorted(random.sample(range(1, max_bonus + 1), nb_bonus))

        bonus_data = convertir_numeros(frame, bonus_cols)
        compte_bonus = Counter()

        for _, ligne in bonus_data.iterrows():
            vals = ligne.dropna().astype(int).tolist()
            vals = [
                n for n in vals
                if 1 <= n <= max_bonus
            ]
            compte_bonus.update(set(vals))

        total_bonus = sum(compte_bonus.values())
        if total_bonus == 0:
            return sorted(random.sample(range(1, max_bonus + 1), nb_bonus))

        poids_bonus = {
            n: max(compte_bonus.get(n, 0) / total_bonus, 0.001)
            for n in range(1, max_bonus + 1)
        }

        result = []
        for _ in range(nb_bonus):
            dispo = [n for n in poids_bonus if n not in result]
            result.append(choisir_pondere(dispo, poids_bonus))

        return sorted(result)

    numeros = construire_numeros()
    bonus = construire_bonus()

    details = []
    for n in numeros:
        details.append({
            "Numero": n,
            "Occurrences historiques": comptes.get(n, 0),
            "Frequence (%)": round(frequences[n] * 100, 2),
            "Retard (tirages)": retards[n],
        })

    return {
        "numeros": numeros,
        "bonus": bonus,
        "details": details,
        "tirages_valides": total,
    }


def generer_cinq_grilles(
    frame,
    colonnes,
    jeu_selectionne,
    mode="mixte",
    utiliser_bonus=True,
    colonnes_bonus=None,
):
    """Construit cinq grilles, avec repetitions limitees."""
    grilles = []
    signatures = set()

    for _ in range(100):
        if len(grilles) >= 5:
            break

        grille = generer_grille_nereon(
            frame=frame,
            colonnes=colonnes,
            jeu_selectionne=jeu_selectionne,
            mode=mode,
            utiliser_bonus=utiliser_bonus,
            colonnes_bonus=colonnes_bonus,
        )

        signature = (
            tuple(grille["numeros"]),
            tuple(grille["bonus"]),
        )

        if signature not in signatures:
            signatures.add(signature)
            grilles.append(grille)

    return grilles


# ============================================================
# INTERFACE DU GENERATEUR
# ============================================================

st.divider()
st.title("🎯 Generateur de grilles Nereon")
st.write(
    "Cinq grilles basees sur les frequences historiques, "
    "les retards observes et un equilibre pair/impair "
    "et petits/grands numeros."
)

if df is None:
    st.info(
        "Importe d'abord une archive historique dans la barre laterale."
    )
else:
    colonnes_disponibles = list(df.columns)
    colonnes_detectees, bonus_detectes, numeriques = (
        detecter_colonnes(df)
    )

    cols_generateur = st.session_state.get(
        "colonnes_numeros", colonnes_detectees
    )
    cols_generateur = [
        c for c in cols_generateur if c in colonnes_disponibles
    ]

    cols_bonus_generateur = st.session_state.get(
        "colonnes_bonus", bonus_detectes
    )
    cols_bonus_generateur = [
        c for c in cols_bonus_generateur
        if c in colonnes_disponibles
    ]

    st.caption(
        "Verifie les colonnes dans l'onglet Fréquences avant "
        "de generer les grilles."
    )

    mode_generation = st.selectbox(
        "Methode d'analyse",
        options=["mixte", "frequences", "retards"],
        format_func=lambda x: {
            "mixte": "Mixte : frequences + retards + equilibre",
            "frequences": "Priorite aux frequences historiques",
            "retards": "Priorite aux retards observes",
        }[x],
        key="mode_generation_nereon",
    )

    inclure_bonus = st.checkbox(
        "Inclure les etoiles / le numero Chance",
        value=True,
        key="bonus_generation_nereon",
    )

    if jeu == "EuroMillions":
        st.caption(
            "EuroMillions : 5 numeros de 1 a 50 et, si active, "
            "2 etoiles de 1 a 12."
        )
    else:
        st.caption(
            "Loto : 5 numeros de 1 a 49 et, si active, "
            "1 numero Chance de 1 a 10."
        )

    if st.button(
        "✨ Generer mes 5 grilles",
        type="primary",
        key="bouton_generer_nereon",
    ):
        try:
            if len(cols_generateur) != 5:
                st.error(
                    "Il faut selectionner exactement cinq colonnes "
                    "de numeros principaux dans l'onglet Fréquences."
                )
            else:
                grilles = generer_cinq_grilles(
                    frame=df,
                    colonnes=cols_generateur,
                    jeu_selectionne=jeu,
                    mode=mode_generation,
                    utiliser_bonus=inclure_bonus,
                    colonnes_bonus=cols_bonus_generateur,
                )

                if len(grilles) < 5:
                    st.warning(
                        "Cinq grilles toutes distinctes n'ont pas pu "
                        "etre creees dans les tentatives effectuees."
                    )

                st.subheader("Tes grilles Néréon")

                for i, grille in enumerate(grilles, start=1):
                    nums = " — ".join(
                        f"{n:02d}" for n in grille["numeros"]
                    )
                    texte = f"Grille {i} : {nums}"

                    if inclure_bonus:
                        label_bonus = (
                            "Etoiles" if jeu == "EuroMillions"
                            else "Chance"
                        )
                        bonus_txt = " — ".join(
                            f"{n:02d}" for n in grille["bonus"]
                        )
                        texte += f" | {label_bonus} : {bonus_txt}"

                    st.markdown(f"**{texte}**")

                st.subheader("Analyse des numéros sélectionnés")
                toutes_details = []

                for i, grille in enumerate(grilles, start=1):
                    for detail in grille["details"]:
                        ligne = dict(detail)
                        ligne["Grille"] = i
                        toutes_details.append(ligne)

                st.dataframe(
                    pd.DataFrame(toutes_details),
                    hide_index=True,
                    use_container_width=True,
                )

                st.info(
                    f"Analyse fondee sur {grilles[0]['tirages_valides']} "
                    "tirages valides. Les grilles sont des selections "
                    "statistiques, pas des predictions gagnantes. "
                    "Dans un tirage equitable, chaque combinaison "
                    "valide conserve la meme probabilite."
                )

        except Exception as exc:
            st.error(f"Impossible de generer les grilles : {exc}")
