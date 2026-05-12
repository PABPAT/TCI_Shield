import streamlit as st
import asyncio
import json
import threading
import os
import tempfile
from voice_agent import run_voice_conversation
from document_extractor import process_uploaded_document
from tci_agent import run_underwriting_from_transcript, issue_policy_from_voice

st.title("Voice Agent")
st.write("Speak to Alex, your AI underwriter.")

# ============================================================
# SESSION STATE INITIALISATION
# ============================================================

for key, default in {
    "voice_transcript":   [],
    "voice_running":      False,
    "voice_done":         False,
    "policy_options":     None,
    "underwriting_result": None,
    "policy_issued":      False,
    "issued_policy":      None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ============================================================
# VOICE CONVERSATION THREAD
# ============================================================

def run_voice_in_thread():
    """Runs voice conversation in background thread."""
    asyncio.run(run_voice_conversation())
    st.session_state.voice_done    = True
    st.session_state.voice_running = False


# ============================================================
# LAYOUT -- TWO COLUMNS
# ============================================================

left, right = st.columns([2, 1])

with left:
    st.subheader("Voice Conversation")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Start Conversation", disabled=st.session_state.voice_running):
            # Reset all state for fresh conversation
            st.session_state.voice_running      = True
            st.session_state.voice_done         = False
            st.session_state.policy_options     = None
            st.session_state.underwriting_result = None
            st.session_state.policy_issued      = False
            st.session_state.issued_policy      = None
            thread = threading.Thread(target=run_voice_in_thread, daemon=True)
            thread.start()

    with col2:
        if st.button("Stop", disabled=not st.session_state.voice_running):
            st.session_state.voice_running = False
            st.session_state.voice_done    = True

    if st.session_state.voice_running:
        st.info("🎤 Alex is listening... Speak now. Click Stop when done.")

    # Show transcript
    if st.session_state.voice_transcript:
        st.subheader("Transcript")
        for entry in st.session_state.voice_transcript:
            with st.chat_message(entry["role"]):
                st.write(entry["content"])

with right:
    st.subheader("Financial Statement")
    st.write("Upload your financial statement when Alex asks for financials.")

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

        st.success("File ready.")

        if st.button("Extract Financial Data"):
            with st.spinner("Reading with Nova Multimodal..."):  # type: ignore
                success, message, financials = process_uploaded_document(tmp_path)
                if success:
                    st.success("Extracted successfully!")
                    st.json(financials)
                else:
                    st.error(f"Extraction failed: {message}")

# ============================================================
# POST-CONVERSATION -- PROCESS TRANSCRIPT
# ============================================================

if st.session_state.voice_done and not st.session_state.policy_options:
    st.divider()
    st.subheader("Processing Your Application")

    with st.spinner("Running underwriting engine..."):  # type: ignore
        # Get voice transcript from voice agent
        from voice_agent import NovaSonicVoiceAgent
        transcript = st.session_state.get("voice_transcript", [])

        if transcript:
            transcript_text = "\n".join([
                f"{'Customer' if t['role'] == 'user' else 'Alex'}: {t['content']}"
                for t in transcript
            ])

            summary_prompt = f"""
            The following is a completed voice conversation where a customer applied
            for trade credit insurance. Extract ALL information and process fully.

            {transcript_text}
            """

            result = run_underwriting_from_transcript(summary_prompt)

            if result and result.get("session_ready"):
                st.session_state.policy_options      = result["policy_options"]
                st.session_state.underwriting_result = result["underwriting_result"]
                st.rerun()
            else:
                st.error("Could not process application. Please check missing information below or use Text Chat.")
        else:
            st.warning("No transcript found. Please complete the voice conversation first.")

# ============================================================
# MISSING DATA
# ============================================================

if os.path.exists("voice_missing.json"):
    with open("voice_missing.json") as f:
        missing_data = json.load(f)

    if not missing_data.get("policy_issued"):
        st.error("Some information was missing from the voice conversation.")
        st.subheader("Missing Information")
        for field in missing_data["missing_fields"].split(","):
            st.write(f"- {field.strip().replace('_', ' ').title()}")
        st.warning("Please go to Text Chat to complete your application.")
        if st.button("Complete in Text Chat"):
            st.switch_page("pages/2_Text_Chat.py")

# ============================================================
# POLICY OPTIONS -- SHOW AFTER UNDERWRITING
# ============================================================

if st.session_state.policy_options and not st.session_state.policy_issued:
    st.divider()

    result = st.session_state.underwriting_result
    if result:
        tier  = result.get("risk_tier", "")
        score = result.get("final_score", 0)

        st.subheader("Underwriting Result")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Risk Tier", tier)
        with col2:
            st.metric("Risk Score", f"{score} / 100")

        if tier == "Declined":
            st.error(f"❌ Application Declined — {result.get('tier_description', '')}")
            st.stop()

    st.subheader("Select Your Policy")
    st.write("Choose the coverage option that suits your business:")

    options = st.session_state.policy_options
    col1, col2, col3 = st.columns(3)

    for col, option_key, label in [
        (col1, "option_1", "Option 1"),
        (col2, "option_2", "Option 2"),
        (col3, "option_3", "Option 3"),
    ]:
        opt = options.get(option_key, {})
        with col:
            st.markdown(f"### {opt.get('name', label)}")
            st.write(f"**Indemnity:** {opt.get('indemnity_percentage', '-')}%")
            st.write(f"**Waiting Period:** {opt.get('waiting_period_days', '-')} days")
            st.write(f"**Political Risk:** {'✅' if opt.get('political_risk') else '❌'}")
            st.write(f"**Single Buyer Cover:** {'✅' if opt.get('single_buyer_cover') else '❌'}")
            st.write(f"**Premium Rate:** {opt.get('premium_rate', '-')}")
            st.write(f"**Annual Premium:** £{opt.get('annual_premium', '-')}")
            st.caption(opt.get("description", ""))

            if st.button(f"Select {label}", key=f"voice_{option_key}"):
                with st.spinner("Issuing policy..."):  # type: ignore
                    policy_result = issue_policy_from_voice(option_key)
                    if "error" in policy_result:
                        st.error(f"Error: {policy_result['error']}")
                    else:
                        st.session_state.policy_issued = True
                        st.session_state.issued_policy = policy_result
                        if os.path.exists("voice_missing.json"):
                            os.remove("voice_missing.json")
                        st.rerun()

# ============================================================
# POLICY CONFIRMATION
# ============================================================

if st.session_state.policy_issued and st.session_state.issued_policy:
    st.divider()
    st.success("✅ Policy Issued Successfully!")

    policy = st.session_state.issued_policy
    col1, col2 = st.columns(2)

    with col1:
        st.metric("Policy ID",   policy.get("policy_id", "-"))
        st.metric("Risk Tier",   policy.get("risk_tier", "-"))
        st.metric("Risk Score",  policy.get("risk_score", "-"))

    with col2:
        st.metric("Start Date",  policy.get("start_date", "-"))
        st.metric("End Date",    policy.get("end_date", "-"))
        st.metric("Customer ID", policy.get("customer_id", "-"))

    if st.button("View Full Policy Summary"):
        st.switch_page("pages/3_Policy_Summary.py")

    if st.button("Start New Application"):
        for key in ["voice_transcript", "voice_running", "voice_done",
                    "policy_options", "underwriting_result",
                    "policy_issued", "issued_policy"]:
            st.session_state[key] = None if key not in ["voice_running", "voice_done", "policy_issued"] else False
        st.rerun()