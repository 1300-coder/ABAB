"""
Reflection Journal — a personal companion that remembers.

Unlike a stateless chatbot, this app keeps a real journal: every check-in
and mood rating is saved to a local SQLite database, so the assistant has
continuity across days, not just within one browser tab.
"""

import sqlite3
from datetime import datetime, date
from pathlib import Path

import pandas as pd
import streamlit as st
import google.generativeai as genai

# ----------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------
DB_PATH = Path(__file__).parent / "journal.db"

PERSONAS = {
    "Warm Encourager": (
        "You are a warm, encouraging journaling companion. You celebrate small "
        "wins, notice progress the person might overlook, and respond with "
        "genuine warmth. Keep responses short (3-5 sentences) and end with a "
        "gentle, open question that invites more reflection."
    ),
    "Reflective Listener": (
        "You are a calm, reflective listener for a personal journal. You mostly "
        "mirror back what the person shares, help them notice patterns across "
        "entries, and rarely give advice unless asked. Keep responses short "
        "(3-5 sentences) and end with an open question."
    ),
    "Practical Coach": (
        "You are a practical, grounded journaling coach. You help the person "
        "turn reflections into one small, concrete next step. Keep responses "
        "short (3-5 sentences), be specific and actionable, and end with a "
        "focused question."
    ),
}

MOOD_LABELS = {
    1: "Very low", 2: "Low", 3: "Low", 4: "A bit low", 5: "Neutral",
    6: "Okay", 7: "Good", 8: "Good", 9: "Great", 10: "Excellent",
}

# ----------------------------------------------------------------------
# Database
# ----------------------------------------------------------------------
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            persona TEXT NOT NULL,
            mood INTEGER NOT NULL,
            user_text TEXT NOT NULL,
            ai_text TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def save_entry(conn, persona, mood, user_text, ai_text):
    conn.execute(
        "INSERT INTO entries (ts, persona, mood, user_text, ai_text) VALUES (?, ?, ?, ?, ?)",
        (datetime.now().isoformat(timespec="seconds"), persona, mood, user_text, ai_text),
    )
    conn.commit()


def fetch_entries(conn, limit=None):
    q = "SELECT ts, persona, mood, user_text, ai_text FROM entries ORDER BY ts DESC"
    if limit:
        q += f" LIMIT {int(limit)}"
    return conn.execute(q).fetchall()


def build_memory_context(conn, n=5):
    """Summarize the last n entries into a short context block for the model."""
    rows = fetch_entries(conn, limit=n)
    if not rows:
        return "This is the person's first entry — you have no prior history yet."
    lines = ["Here is a brief record of the person's recent journal entries (most recent first):"]
    for ts, _, mood, user_text, _ in rows:
        d = ts.split("T")[0]
        snippet = user_text.strip().replace("\n", " ")
        if len(snippet) > 160:
            snippet = snippet[:160] + "..."
        lines.append(f"- {d} (mood {mood}/10): {snippet}")
    return "\n".join(lines)


# ----------------------------------------------------------------------
# Page setup
# ----------------------------------------------------------------------
st.set_page_config(page_title="Reflection Journal", page_icon="🖋️", layout="centered")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,500;0,600;1,500&family=Inter:wght@400;500;600&display=swap');
    html, body, [class*="css"]  { font-family: 'Inter', sans-serif; }
    h1, h2, h3, .journal-title { font-family: 'Lora', serif; }
    .journal-title {
        font-size: 2.1rem;
        font-weight: 600;
        color: #1E2B32;
        margin-bottom: 0;
    }
    .journal-sub {
        color: #5B6B72;
        font-size: 0.95rem;
        margin-top: 0.1rem;
        margin-bottom: 1.4rem;
    }
    .stChatMessage { border-radius: 12px; }
    </style>
    <div class="journal-title">🖋️ Reflection Journal</div>
    <div class="journal-sub">A private space that remembers what you tell it.</div>
    """,
    unsafe_allow_html=True,
)

conn = get_conn()

# ----------------------------------------------------------------------
# Sidebar: API key, persona, mood, history, export
# ----------------------------------------------------------------------
api_key = st.secrets.get("GOOGLE_API_KEY", None) if hasattr(st, "secrets") else None

with st.sidebar:
    st.header("Settings")
    if not api_key:
        api_key = st.text_input("Google Gemini API key", type="password")
    else:
        st.success("API key loaded from secrets.toml")

    persona = st.selectbox("Companion style", list(PERSONAS.keys()))

    st.divider()
    st.subheader("Today's check-in")
    mood = st.slider("How are you feeling right now?", 1, 10, 5)
    st.caption(f"**{MOOD_LABELS[mood]}**")

    st.divider()
    st.subheader("Mood trend")
    rows = fetch_entries(conn, limit=30)
    if rows:
        df = pd.DataFrame(rows, columns=["ts", "persona", "mood", "user_text", "ai_text"])
        df["ts"] = pd.to_datetime(df["ts"])
        df = df.sort_values("ts")
        st.line_chart(df.set_index("ts")["mood"], height=160)
    else:
        st.caption("Your mood trend will appear here after your first entry.")

    st.divider()
    with st.expander("📖 Past entries"):
        all_rows = fetch_entries(conn, limit=50)
        if not all_rows:
            st.caption("No entries yet.")
        for ts, p, m, user_text, ai_text in all_rows:
            d = ts.replace("T", " ")
            st.markdown(f"**{d}** · mood {m}/10 · _{p}_")
            st.markdown(f"> {user_text}")
            st.caption(ai_text)
            st.markdown("---")

    if rows:
        export_lines = ["# My Reflection Journal\n"]
        for ts, p, m, user_text, ai_text in reversed(fetch_entries(conn)):
            export_lines.append(f"## {ts.replace('T', ' ')} (mood {m}/10, {p})\n")
            export_lines.append(f"**Me:** {user_text}\n")
            export_lines.append(f"**Companion:** {ai_text}\n")
        st.download_button(
            "⬇️ Export journal (.md)",
            "\n".join(export_lines),
            file_name=f"journal_export_{date.today().isoformat()}.md",
            mime="text/markdown",
        )

    st.divider()
    st.caption(
        "This is a private reflection tool, not a substitute for professional "
        "mental health care. If you're in crisis, please reach out to a "
        "counselor, doctor, or local crisis line."
    )

if not api_key:
    st.info("Enter your Gemini API key in the sidebar to begin.")
    st.stop()

# ----------------------------------------------------------------------
# Configure Gemini
# ----------------------------------------------------------------------
try:
    genai.configure(api_key=api_key)
except Exception as e:
    st.error(f"Failed to configure Gemini: {e}")
    st.stop()

memory_context = build_memory_context(conn, n=5)
system_instruction = PERSONAS[persona] + "\n\n" + memory_context

# Re-create the chat session whenever the persona changes, so the system
# instruction (and injected memory) stays accurate.
if (
    "chat_session" not in st.session_state
    or st.session_state.get("persona_used") != persona
):
    try:
        model = genai.GenerativeModel(
            "gemini-2.0-flash", system_instruction=system_instruction
        )
        st.session_state.chat_session = model.start_chat(history=[])
        st.session_state.persona_used = persona
        st.session_state.messages = []
    except Exception as e:
        st.error(f"Failed to start chat session: {e}")
        st.stop()

if "messages" not in st.session_state:
    st.session_state.messages = []

# ----------------------------------------------------------------------
# Render chat history (this session only — full history lives in sidebar)
# ----------------------------------------------------------------------
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ----------------------------------------------------------------------
# Chat input
# ----------------------------------------------------------------------
placeholder_text = "What's on your mind today?"
user_prompt = st.chat_input(placeholder_text)

if user_prompt:
    st.session_state.messages.append({"role": "user", "content": user_prompt})
    with st.chat_message("user"):
        st.markdown(user_prompt)

    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        full_response = ""
        try:
            response = st.session_state.chat_session.send_message(
                user_prompt, stream=True
            )
            for chunk in response:
                if chunk.text:
                    full_response += chunk.text
                    response_placeholder.markdown(full_response + "▌")
            response_placeholder.markdown(full_response)
        except Exception as e:
            full_response = f"⚠️ Error: {e}"
            response_placeholder.markdown(full_response)

    st.session_state.messages.append({"role": "assistant", "content": full_response})

    # Persist to the journal database
    try:
        save_entry(conn, persona, mood, user_prompt, full_response)
    except Exception as e:
        st.warning(f"Couldn't save this entry to your journal: {e}")
