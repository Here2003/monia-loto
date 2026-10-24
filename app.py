
import streamlit as st
from openai import OpenAI, OpenAIError

st.set_page_config(
    page_title="MonIA — Assistant intelligent",
    page_icon="🧠",
    layout="centered",
)

st.title("🧠 MonIA")
st.caption("Ton assistant intelligent personnel")

st.info(
    "MonIA peut discuter, expliquer des analyses et t'aider à "
    "étudier les tirages. Il ne peut pas prédire les résultats "
    "aléatoires d'une loterie."
)

# La clé reste dans les secrets de Streamlit, pas dans GitHub.
try:
    api_key = st.secrets["OPENAI_API_KEY"]
except Exception:
    api_key = ""

try:
    model = st.secrets.get("OPENAI_MODEL", "gpt-5.5")
except Exception:
    model = "gpt-5.5"

if not api_key:
    st.error(
        "Clé API absente. Ajoute OPENAI_API_KEY dans "
        "Manage app → Settings → Secrets sur Streamlit."
    )
    st.stop()

client = OpenAI(api_key=api_key, timeout=60.0)

INSTRUCTIONS = """
Tu es MonIA, un assistant intelligent qui parle français.
Tu es clair, méthodique, prudent et transparent.
Tu aides à comprendre les données, les statistiques et les probabilités.

Pour EuroMillions et le Loto :
- Distingue toujours les faits mesurés des hypothèses.
- N'invente jamais de tirages, de gagnants, de montants ou de sources.
- Explique que les tirages sont aléatoires et que les fréquences
  historiques ne permettent pas de prédire le prochain tirage.
- Si tu ne disposes pas des données nécessaires, dis-le clairement.
- Présente les calculs et les limites de tes conclusions.
"""

if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.subheader("Conversation")
    st.write(f"Modèle configuré : `{model}`")
    if st.button("Effacer la conversation"):
        st.session_state.messages = []
        st.rerun()

    st.caption(
        "L'historique est conservé dans la session actuelle. "
        "Il peut disparaître si la session est réinitialisée."
    )

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

question = st.chat_input("Pose ta question à MonIA…")

if question:
    st.session_state.messages.append({
        "role": "user",
        "content": question,
    })

    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("MonIA réfléchit…"):
            try:
                response = client.responses.create(
                    model=model,
                    instructions=INSTRUCTIONS,
                    input=[
                        {
                            "role": m["role"],
                            "content": m["content"],
                        }
                        for m in st.session_state.messages
                    ],
                )

                answer = response.output_text

                if not answer:
                    answer = (
                        "Le modèle n'a pas renvoyé de texte. "
                        "Essaie de reformuler ta question."
                    )

                st.markdown(answer)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer,
                })

            except OpenAIError as erreur:
                st.error(
                    "L'API n'a pas pu répondre. Vérifie la clé, "
                    "le modèle sélectionné et la facturation API."
                )
                st.caption(str(erreur))

            except Exception as erreur:
                st.error("Une erreur inattendue est survenue.")
                st.caption(str(erreur))
