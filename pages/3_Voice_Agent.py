import streamlit as st
import asyncio
import json
import threading
import os
import tempfile
from voice_agent import run_voice_conversation
from document_extractor import process_uploaded_document

st.title("Voice Agent")
st.write("Speak to Alex, your AI underwriter.")

if "voice_transcript" not in st.session_state:
    st.session_state.voice_transcript = []

if "voice_running" not in st.session_state:
    st.session_state.voice_running = False

if "voice_done" not in st.session_state:
    st.session_state.voice_done = False


def run_voice_in_thread():
    asyncio.run(run_voice_conversation())
    st.session_state.voice_done = True


# Two column layout -- voice on left, upload on right
left, right = st.columns([2, 1])

with left:
    st.subheader("Voice Conversation")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Start Conversation", disabled=st.session_state.voice_running):
            st.session_state.voice_running = True
            st.session_state.voice_done = False
            thread = threading.Thread(target=run_voice_in_thread, daemon=True)
            thread.start()

    with col2:
        if st.button("Stop", disabled=not st.session_state.voice_running):
            st.session_state.voice_running = False

    if st.session_state.voice_running:
        st.info("🎤 Alex is listening... Speak now.")

    if st.session_state.voice_done:
        st.success("Conversation complete. Underwriting in progress...")

    if st.session_state.voice_transcript:
        st.subheader("Transcript")
        for entry in st.session_state.voice_transcript:
            role = "Alex" if entry["role"] == "assistant" else "You"
            with st.chat_message(entry["role"]):
                st.write(entry["content"])

with right:
    st.subheader("Financial Statement")
    st.write("When Alex asks for financials, upload your statement here instead.")

    uploaded_file = st.file_uploader(
        "Upload (PDF, DOCX, XLSX, CSV)",
        type=["pdf", "docx", "xlsx", "csv", "txt"]
    )

    if uploaded_file:
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=os.path.splitext(uploaded_file.name)[1]
        ) as tmp:
            tmp.write(uploaded_file.read())
            tmp_path = tmp.name

        st.success("File ready. Click below to extract.")

        if st.button("Extract Financial Data"):
            with st.spinner("Reading with Nova Multimodal..."):  # type: ignore
                success, message, financials = process_uploaded_document(tmp_path)
                if success:
                    st.success("Extracted successfully!")
                    st.json(financials)
                    st.info("Financial data is ready. Alex will use it for underwriting when the conversation ends.")
                else:
                    st.error(f"Extraction failed: {message}")

if os.path.exists("voice_missing.json"):
    with open("voice_missing.json") as f:
        missing_data = json.load(f)

    if not missing_data.get("policy_issued"):
        st.error("Your application could not be completed — some information was missing from the voice conversation.")
        st.subheader("Missing Information")
        for field in missing_data["missing_fields"].split(","):
            st.write(f"- {field.strip().replace('_', ' ').title()}")
        st.warning("Please go to Text Chat to provide the missing details and complete your application.")
        if st.button("Complete in Text Chat"):
            st.switch_page("pages/2_Text_Chat.py")
    else:
        st.success("Policy issued successfully! Check Policy Summary page.")
        if os.path.exists("voice_missing.json"):
            os.remove("voice_missing.json")