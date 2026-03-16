import streamlit as st
import re
import os
import tempfile
from tci_agent import reset_session, SYSTEM_PROMPT, nova_lite
from tci_agent import get_progress, set_buyer_count, collect_business_info
from tci_agent import collect_buyer_info, upload_financial_document
from tci_agent import collect_financial_data, run_underwriting
from tci_agent import generate_policy_options, issue_policy
from strands import Agent


def clean(text: str) -> str:
    return re.sub(r"<thinking>.*?</thinking>", "", str(text), flags=re.DOTALL).strip()


st.title("Text Chat")
st.write("Chat with Alex, your AI underwriter.")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "agent" not in st.session_state:
    reset_session()
    st.session_state.agent = Agent(
        model=nova_lite,
        system_prompt=SYSTEM_PROMPT,
        callback_handler=None,
        tools=[
            get_progress,
            set_buyer_count,
            collect_business_info,
            collect_buyer_info,
            upload_financial_document,
            collect_financial_data,
            run_underwriting,
            generate_policy_options,
            issue_policy,
        ],
    )
    opening = clean(st.session_state.agent(
        "Hello, I would like to apply for trade credit insurance."
    ))
    st.session_state.chat_history.append({
        "role": "assistant",
        "content": opening
    })

for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

user_input = st.chat_input("Type your message...")

if user_input:
    st.session_state.chat_history.append({
        "role": "user",
        "content": user_input
    })
    with st.chat_message("user"):
        st.write(user_input)

    response_text = clean(st.session_state.agent(user_input))

    st.session_state.chat_history.append({
        "role": "assistant",
        "content": response_text
    })
    with st.chat_message("assistant"):
        st.write(response_text)

st.divider()
st.subheader("Upload Financial Statement")
uploaded_file = st.file_uploader(
    "Upload your financial statement (PDF, DOCX, XLSX, CSV)",
    type=["pdf", "docx", "xlsx", "csv", "txt"]
)

if uploaded_file:
    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=os.path.splitext(uploaded_file.name)[1]
    ) as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name

    if st.button("Extract Financial Data from Document"):
        with st.spinner("Reading document with Nova Multimodal..."):  # type: ignore
            response_text = clean(st.session_state.agent(
                f"The customer has uploaded a financial statement. "
                f"Please extract the financial figures using the upload_financial_document tool. "
                f"File path: {tmp_path}"
            ))
            st.success("Financial data extracted!")
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": response_text
            })
            st.rerun()

if st.button("Start New Conversation"):
    reset_session()
    st.session_state.chat_history = []
    del st.session_state.agent
    st.rerun()