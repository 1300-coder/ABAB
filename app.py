import streamlit as st
import google.generativeai as genai

# ----------------------------------------------------------------------
# Page config
# ----------------------------------------------------------------------
st.set_page_config(page_title="Gemini Chatbot", page_icon="🤖", layout="centered")
st.title("🤖 Gemini AI Chatbot")

# ----------------------------------------------------------------------
# API Key handling
# ----------------------------------------------------------------------
# Preferred: put your key in .streamlit/secrets.toml as:
#   GOOGLE_API_KEY = "your-key-here"
# Falls back to a sidebar text input if no secret is found (useful for
# local testing or Streamlit Community Cloud deployments without secrets set).

api_key = st.secrets.get("GOOGLE_API_KEY", None) if hasattr(st, "secrets") else None

with st.sidebar:
    st.header("Settings")
    if not api_key:
        api_key = st.text_input("Enter your Google Gemini API Key", type="password")
    else:
        st.success("API key loaded from secrets.toml")

    model_name = st.selectbox(
        "Model",
        ["gemini-1.5-flash"],
        index=0,
    )

    if st.button("Clear chat"):
        st.session_state.pop("chat_session", None)
        st.session_state.pop("messages", None)
        st.rerun()

if not api_key:
    st.warning("Please enter your Google Gemini API key in the sidebar to start chatting.")
    st.stop()

# ----------------------------------------------------------------------
# Configure Gemini
# ----------------------------------------------------------------------
try:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
except Exception as e:
    st.error(f"Failed to configure Gemini: {e}")
    st.stop()

# ----------------------------------------------------------------------
# Session state: keep chat history + a persistent chat session
# ----------------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []  # list of {"role": "user"/"assistant", "content": str}

if "chat_session" not in st.session_state:
    st.session_state.chat_session = model.start_chat(history=[])

# ----------------------------------------------------------------------
# Render existing chat history
# ----------------------------------------------------------------------
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ----------------------------------------------------------------------
# Chat input + response
# ----------------------------------------------------------------------
user_prompt = st.chat_input("Type your message...")

if user_prompt:
    # Show user message immediately
    st.session_state.messages.append({"role": "user", "content": user_prompt})
    with st.chat_message("user"):
        st.markdown(user_prompt)

    # Get and show assistant response
    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_response = ""
        try:
            response = st.session_state.chat_session.send_message(
                user_prompt, stream=True
            )
            for chunk in response:
                if chunk.text:
                    full_response += chunk.text
                    placeholder.markdown(full_response + "▌")
            placeholder.markdown(full_response)
        except Exception as e:
            full_response = f"⚠️ Error: {e}"
            placeholder.markdown(full_response)

    st.session_state.messages.append({"role": "assistant", "content": full_response})
