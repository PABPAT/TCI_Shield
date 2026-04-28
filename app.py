import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="TCI Shield",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🛡️ TCI Shield")
st.subheader("AI-Powered Trade Credit Insurance Underwriting")

st.markdown("""
Welcome to **TCI Shield** — trade credit insurance underwriting powered by Amazon Nova.

---

### How It Works

1. 🎤 **Voice Agent** — Speak to Alex, your AI underwriter, and apply by voice
2. 💬 **Text Chat** — Chat with Alex in text if you prefer typing
3. 📄 **Policy Summary** — View your latest issued policy
4. 📊 **Dashboard** — View all policies issued

---

### Get Started

Use the **sidebar** to navigate to any section.
""")

st.info("Select a page from the sidebar to get started")