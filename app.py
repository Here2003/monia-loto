import io
import itertools
import math
import zipfile
from collections import Counter
from datetime import datetime, timezone

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
    """Essaie plusieurs encodages et séparateurs pour lire CSV/TXT."""
    erreurs = []
    for encodage in ("utf-8-sig", "cp1252", "latin1"):
        try:
            texte = contenu.decode(encodage)
        except UnicodeDecodeError as exc:
            erreurs.append(str(exc))
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
                    frame.columns = [str(c).strip() for c in frame.columns]
                    return frame
            except Exception as exc:
                erreurs.append(str(exc))
    raise ValueError(f"Impossible de lire {nom} comme CSV/TXT.")


def lire_fichier(nom, contenu):
    nom_bas = nom.lower()
    if nom_bas.endswith(".zip"):
        frames = []
        with zipfile.ZipFile(io.BytesIO(contenu)) as archive:
            for interne in archive.namelist():
                if interne.lower().endswith((".csv", ".txt")):
                    try:
                        frames.append(lire_table(interne, archive.read(interne)))
                    except Exception:
                        continue
        if not frames:
            raise ValueError("Aucun fichier CSV/TXT lisible dans cette archive ZIP.")
        return frames
    if nom_bas.endswith((".csv", ".txt")):
        return [lire_table(nom, contenu)]
    raise ValueError("Format non pris en charge. Utilise CSV, TXT ou ZIP.")


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
    """Détection indicative basée sur les noms; l'utilisateur peut corriger."""
    numeriques = []
    for col in frame.columns:
        vals = pd.to_numeric(frame[col], errors="coerce")
