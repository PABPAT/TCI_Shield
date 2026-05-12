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
    "voice_transcript":     [],
    "voice_running":        False,
    "voice_done":           False,
    "policy_options":       None,
    "underwriting_result":  None,
    "policy_issued":        False,
    "issued_policy":        None,
    "extracted_financials": None,
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
            st.session_state.extracted_financials = None
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
    st.caption("Once uploaded, figures will be used automatically — no need to read them out.")

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

        if st.button("Extract Financial Data"):
            with st.spinner("Reading with Nova Multimodal..."):  # type: ignore
                success, message, financials = process_uploaded_document(tmp_path)
                if success:
                    st.success("✅ Financial data extracted successfully!")
                    st.session_state.extracted_financials = financials
                    # Also store directly in tci_agent session as backup
                    from tci_agent import session
                    session["financials"] = financials
                    session["progress"]["financials_collected"] = True
                    st.info("Financial figures are ready and will be used automatically in underwriting.")
                    # Show extracted figures
                    with st.expander("View extracted figures"):
                        for field, value in financials.items():
                            st.write(f"**{field.replace('_', ' ').title()}:** £{float(value):,.0f}")
                else:
                    st.error(f"Extraction failed: {message}")
                    st.warning("Please provide financial figures verbally to Alex during the conversation.")

    # Show status if financials already extracted
    if st.session_state.extracted_financials:
        st.success("✅ Financials ready for underwriting")


# ============================================================
# POST-CONVERSATION -- PROCESS TRANSCRIPT
# ============================================================

if st.session_state.voice_done and not st.session_state.policy_options:
    st.divider()
    st.subheader("Processing Your Application")

    with st.spinner("Running underwriting engine..."):  # type: ignore
        transcript = st.session_state.get("voice_transcript", [])

        if transcript:
            # Build transcript text
            transcript_text = "\n".join([
                f"{'Customer' if t['role'] == 'user' else 'Alex'}: {t['content']}"
                for t in transcript
            ])

            # Inject extracted financials into transcript if available
            # This ensures Nova Lite sees the figures without asking again
            if st.session_state.get("extracted_financials"):
                fin = st.session_state.extracted_financials
                financial_injection = f"""
Alex: I can see you have uploaded your financial statement. I have extracted the following figures from your document.
Customer: Annual revenue {fin.get('annual_revenue', 0)}, current assets {fin.get('current_assets', 0)}, current liabilities {fin.get('current_liabilities', 0)}, total liabilities {fin.get('total_liabilities', 0)}, tangible net worth {fin.get('tangible_net_worth', 0)}, total assets {fin.get('total_assets', 0)}, capital {fin.get('capital', 0)}, bad debts {fin.get('bad_debts', 0)}, debtors {fin.get('debtors', 0)}, creditors {fin.get('creditors', 0)}, cost of sales {fin.get('cost_of_sales', 0)}.
Alex: Thank you. I now have all 11 financial figures from your uploaded statement.
"""
                transcript_text += financial_injection
                logging.info = lambda msg: None  # suppress logging in UI context

            summary_prompt = f"""
            The following is a completed voice conversation where a customer applied
            for trade credit insurance. Extract ALL information and process fully.

            {transcript_text}

            INSTRUCTIONS:
            1. Extract ALL information from the transcript
            2. Call set_buyer_count with the number of buyers
            3. Call collect_business_info with all business details
            4. Call collect_buyer_info with all buyer details
            5. Call collect_financial_data with the financial figures shown in the transcript
            6. Call run_underwriting immediately
            7. Call generate_policy_options immediately
            8. STOP after generate_policy_options -- do NOT call issue_policy
            9. Do NOT ask any questions -- just process the transcript
            10. If any data is missing write MISSING_DATA: followed by missing fields
            """

            result = run_underwriting_from_transcript(
                summary_prompt,
                extracted_financials=st.session_state.get("extracted_financials")
            )

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

    options       = st.session_state.policy_options
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
        st.metric("Policy ID",   policy.get("policy_id",   "-"))
        st.metric("Risk Tier",   policy.get("risk_tier",   "-"))
        st.metric("Risk Score",  policy.get("risk_score",  "-"))

    with col2:
        st.metric("Start Date",  policy.get("start_date",  "-"))
        st.metric("End Date",    policy.get("end_date",    "-"))
        st.metric("Customer ID", policy.get("customer_id", "-"))

    if st.button("View Full Policy Summary"):
        st.switch_page("pages/3_Policy_Summary.py")

    if st.button("Start New Application"):
        for key in [
            "voice_transcript", "voice_done", "policy_options",
            "underwriting_result", "issued_policy", "extracted_financials"
        ]:
            st.session_state[key] = [] if key == "voice_transcript" else None
        st.session_state.voice_running = False
        st.session_state.policy_issued = False
        st.rerun()