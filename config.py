# ============================================================
# TRADE CREDIT INSURANCE — CONFIGURATION
# ============================================================
# Store all API keys and configuration here.
# NEVER commit this file to GitHub or share it publicly.
# Add config.py to your .gitignore file.
# ============================================================
import os
from dotenv import load_dotenv

load_dotenv()
COMPANIES_HOUSE_API_KEY = os.getenv("COMPANIES_HOUSE_API_KEY")
APP_PASSWORD = os.getenv("APP_PASSWORD")
COMPANIES_HOUSE_BASE_URL = "https://api.company-information.service.gov.uk"

# AWS Configuration
AWS_REGION = "us-east-1"

# Nova Model IDs
NOVA_LITE_MODEL_ID   = "amazon.nova-lite-v1:0"
NOVA_SONIC_MODEL_ID  = "amazon.nova-sonic-v1:0"

# DynamoDB Table Names
TABLE_CUSTOMERS = "tci_customers"
TABLE_BUYERS    = "tci_buyers"