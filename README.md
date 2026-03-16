# TCI Shield

AI-powered trade credit insurance underwriting using Amazon Nova.

## Overview

TCI Shield is a voice and text-based trade credit insurance underwriting agent. A business owner speaks to Alex, an AI underwriter powered by Amazon Nova 2 Sonic, provides their business and buyer details, and receives a policy — entirely through conversation.

## Architecture

```
Voice (Nova 2 Sonic)     Text Chat (Nova Lite)
        |                        |
        |                        |
        +-----------+------------+
                    |
            Strands Agent
            (Nova Lite)
                    |
        +-----------+------------+
        |           |            |
  Underwriting   Document     DynamoDB
   Engine       Extractor
  (Risk Score)  (Nova         (Policies)
                Multimodal)
```

## Nova Models Used

- **Amazon Nova 2 Sonic** — real-time bidirectional voice conversation
- **Amazon Nova Lite** — agent reasoning and underwriting orchestration
- **Amazon Nova Multimodal** — financial document extraction (PDF, DOCX, XLSX)

## Features

- Voice-based insurance application via Amazon Nova 2 Sonic
- Text chat application via AWS Strands Agents and Nova Lite
- Automated risk scoring engine with 6 weighted dimensions
- Financial document extraction using Nova Multimodal
- Policy generation with 3 coverage options
- Policy issuance and storage in AWS DynamoDB
- Streamlit UI with voice agent, text chat, policy summary, and dashboard

## Risk Scoring Model

The underwriting engine scores risk across 6 dimensions:

- Industry risk
- Buyer country risk
- Financial health ratios
- Payment terms
- Portfolio concentration
- Loss history

Scores map to 4 policy tiers: Standard, Enhanced, High Risk, or Declined.

## Project Structure

```
Trade_Credit_Agent/
    app.py                      # Streamlit entry point
    pages/
        1_Voice_Agent.py        # Nova Sonic voice interface
        2_Text_Chat.py          # Nova Lite text chat
        3_Policy_Summary.py     # Latest policy view
        4_Dashboard.py          # All policies dashboard
    tci_agent.py                # Strands Agent + underwriting tools
    voice_agent.py              # Nova Sonic bidirectional streaming
    underwriting_engine.py      # Risk scoring engine
    document_extractor.py       # Nova Multimodal document extraction
    database.py                 # DynamoDB operations
    models.py                   # Pydantic validation models
    config.py                   # AWS configuration
    .env.example                # Environment variables template
```

## Setup

### Prerequisites

- Python 3.13
- AWS account with Bedrock access
- AWS CLI configured with `aws configure`

### Installation

```bash
git clone https://github.com/PABPAT/TCI_Shield.git
cd TCI_Shield
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

```
COMPANIES_HOUSE_API_KEY=your_key_here
```

### AWS Setup

```bash
aws configure
```

Enter your AWS access key, secret key, and set region to `us-east-1`.

Enable these models in AWS Bedrock console:
- `amazon.nova-lite-v1:0`
- `amazon.nova-2-sonic-v1:0`

### Run

```bash
streamlit run app.py
```

Open `http://localhost:8501` in your browser.

## Dependencies

```
strands-agents
strands-agents-tools
boto3
aws-sdk-bedrock-runtime
smithy-aws-core
pyaudio
pydantic
streamlit
python-dotenv
```

## Built With

- Amazon Nova 2 Sonic
- Amazon Nova Lite
- Amazon Nova Multimodal
- AWS Strands Agents
- AWS Bedrock
- AWS DynamoDB
- Python 3.13
- Streamlit

## Hackathon

Built for the [Amazon Nova AI Hackathon](https://amazon-nova.devpost.com/) — March 2026.

Category: Voice AI + Agentic AI
