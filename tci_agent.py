# ============================================================
# TRADE CREDIT INSURANCE -- STRANDS AGENT
# ============================================================
# Orchestrates the full underwriting conversation using
# AWS Strands Agents framework with Amazon Nova Lite.
#
# Agent Flow:
#   1. Intake     -- collect business info via conversation
#   2. Underwrite -- run risk scoring engine
#   3. Price      -- generate policy options
#   4. Issue      -- confirm and save policy
#
# Each step is a @tool that the Orchestrator calls
# automatically based on conversation context.
# ============================================================

import logging
import json
import re
from datetime import datetime, timedelta
from decimal import Decimal

from strands import Agent, tool
from strands.models.bedrock import BedrockModel

from underwriting_engine import calculate_risk_score
from database import save_customer, save_buyer, add_policy_to_customer, generate_policy_id
from config import NOVA_LITE_MODEL_ID, AWS_REGION
from models import BusinessInfo, BuyerInfo, FinancialData, validate_model
from document_extractor import process_uploaded_document

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

# ============================================================
# SECTION 1 -- NOVA LITE MODEL CONFIGURATION
# ============================================================

nova_lite = BedrockModel(
    model_id=NOVA_LITE_MODEL_ID,
    region_name=AWS_REGION,
)

# ============================================================
# SECTION 2 -- SESSION STATE
# ============================================================

session = {
    "customer_id":              None,
    "business_name":            None,
    "industries":               [],
    "trade_type":               None,
    "annual_turnover":          None,
    "credit_sales_percentage":  None,
    "buyer_countries":          [],
    "top_buyer_percentage":     None,
    "payment_terms_days":       None,
    "loss_ratio":               None,
    "years_in_business":        None,
    "buyers":                   [],
    "financials":               None,
    "underwriting_result":      None,
    "selected_policy":          None,
    "intake_complete":          False,
    "customer_country":         None,
    "customer_country_code":    None,
    "declared_buyer_count":     None,

    # Progress tracking -- records what has been collected
    # Used by tools to report back what is still missing
    "progress": {
        "business_collected":   False,
        "buyers_collected":     False,
        "financials_collected": False,
        "underwriting_done":    False,
        "policy_issued":        False,
    }
}

# ============================================================
# SECTION 3 -- RESPONSE HELPER & VALIDATORS
# ============================================================

def extract_text(response) -> str:
    """
    Extracts clean text from Strands AgentResult.
    callback_handler=None means Strands does not print anything.
    We read the final response from response.message after completion.
    Strips thinking tags before displaying to user.
    """
    try:
        msg = response.message
        if not isinstance(msg, dict):
            return str(response)
        content = msg.get("content", [])
        if not isinstance(content, list):
            return str(response)
        for block in content:
            if isinstance(block, dict) and "text" in block:
                text = str(block.get("text", ""))
                text = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL)
                return text.strip()
        return str(response)
    except (AttributeError, KeyError, TypeError) as e:
        logging.warning(f"extract_text failed: {e}")
        return str(response)


def validate_business_info() -> str | None:
    """
    Validates all required business info fields are collected.
    Returns error message string if any field is missing, else None.
    """
    checks = [
        (not session.get("business_name"),           "Business name is missing"),
        (not session.get("industries"),              "Industry is missing"),
        (not session.get("trade_type"),              "Trade type is missing"),
        (not session.get("annual_turnover"),         "Annual turnover is missing"),
        (not session.get("credit_sales_percentage"), "Credit sales percentage is missing"),
        (not session.get("years_in_business"),       "Years in business is missing"),
        (not session.get("customer_country"),        "Customer country is missing"),
        (not session.get("customer_country_code"),   "Customer country code is missing"),
    ]
    missing = [msg for condition, msg in checks if condition]
    if missing:
        return f"Missing business info: {', '.join(missing)}"
    return None


def validate_buyer_info() -> str | None:
    """
    Validates all required buyer info fields are collected.
    Returns error message string if any field is missing, else None.
    """
    checks = [
        (not session.get("buyers"),                   "Buyer details are missing"),
        (len(session.get("buyers", [])) == 0,         "No buyers collected"),
        (not session.get("buyer_countries"),          "Buyer countries are missing"),
        (session.get("top_buyer_percentage") is None, "Top buyer percentage is missing"),
        (session.get("payment_terms_days") is None,   "Payment terms are missing"),
        (session.get("loss_ratio") is None,           "Loss ratio is missing"),
        (not session.get("declared_buyer_count"),     "Declared buyer count is missing -- ask how many buyers first"),
    ]
    missing = [msg for condition, msg in checks if condition]
    if missing:
        return f"Missing buyer info: {', '.join(missing)}"

    # Validate collected count matches declared count
    declared = session.get("declared_buyer_count", 0)
    collected = len(session.get("buyers", []))
    if declared and collected != declared:
        return f"Buyer count mismatch -- declared {declared} but only {collected} collected"

    # Validate each buyer has required fields
    for i, buyer in enumerate(session.get("buyers", []), 1):
        buyer_checks = [
            (not buyer.get("name"),            f"Buyer {i} name is missing"),
            (not buyer.get("country"),         f"Buyer {i} country is missing"),
            (not buyer.get("country_code"),    f"Buyer {i} country code is missing"),
            (not buyer.get("industry"),        f"Buyer {i} industry is missing"),
            (not buyer.get("exposure_amount"), f"Buyer {i} exposure amount is missing"),
        ]
        buyer_missing = [msg for condition, msg in buyer_checks if condition]
        if buyer_missing:
            return f"Incomplete buyer data: {', '.join(buyer_missing)}"

    return None


def validate_financial_data() -> str | None:
    """
    Validates all required financial figures are collected.
    Returns error message string if any field is missing, else None.
    """
    financials = session.get("financials")
    if not financials:
        return "Financial data is missing -- ask customer for all 11 financial figures"

    required_fields = [
        "annual_revenue",
        "current_assets",
        "current_liabilities",
        "total_liabilities",
        "tangible_net_worth",
        "total_assets",
        "capital",
        "bad_debts",
        "debtors",
        "creditors",
        "cost_of_sales",
    ]
    missing = [f for f in required_fields if financials.get(f) is None]
    if missing:
        return f"Missing financial figures: {', '.join(missing)}"

    # Check key figures are non-zero (except TNW which can be negative)
    zero_checks = [
        (financials.get("annual_revenue", 0) <= 0,  "Annual revenue must be greater than 0"),
        (financials.get("total_assets", 0) <= 0,    "Total assets must be greater than 0"),
        (financials.get("current_assets", 0) <= 0,  "Current assets must be greater than 0"),
    ]
    invalid = [msg for condition, msg in zero_checks if condition]
    if invalid:
        return f"Invalid financial figures: {', '.join(invalid)}"

    return None


def validate_all() -> str | None:
    """
    Runs all validations in sequence.
    Returns first error found, or None if all data is valid.
    """
    return (
        validate_business_info() or
        validate_buyer_info()    or
        validate_financial_data()
    )


# ============================================================
# SECTION 4 -- TOOLS
# ============================================================

@tool
def set_buyer_count(total_buyers: int) -> str:
    """
    Stores the total number of buyers declared by the customer.
    Call this tool immediately after Step 7 when customer tells
    you how many buyers they have.
    This count is used to verify all buyers are collected before
    calling collect_buyer_info.

    Args:
        total_buyers: total number of buyers declared by customer -- must be > 0

    Returns confirmation of buyer count stored.
    """
    if not total_buyers or total_buyers <= 0:
        return json.dumps({"error": "Total buyers must be greater than 0"})

    session["declared_buyer_count"] = total_buyers
    logging.info(f"Declared buyer count set: {total_buyers}")

    return json.dumps({
        "status":               "stored",
        "declared_buyer_count": total_buyers,
        "message":              f"Customer has {total_buyers} buyers. Collect details for each one before calling collect_buyer_info."
    })


@tool
def get_progress() -> str:
    """
    Returns current collection progress.
    Call this tool if you are unsure what has been collected
    or what step to proceed to next.

    Returns status of all 5 collection stages.
    """
    progress = session.get("progress", {})
    missing  = validate_all()

    return json.dumps({
        "business_collected":   progress.get("business_collected",   False),
        "buyers_collected":     progress.get("buyers_collected",     False),
        "financials_collected": progress.get("financials_collected", False),
        "underwriting_done":    progress.get("underwriting_done",    False),
        "policy_issued":        progress.get("policy_issued",        False),
        "next_action":          missing if missing else "All data collected -- ready to proceed",
        "declared_buyer_count": session.get("declared_buyer_count", 0),
        "buyers_collected_count": len(session.get("buyers", [])),
        "buyers_remaining":     (session.get("declared_buyer_count", 0) - len(session.get("buyers", []))),
    })


@tool
def collect_business_info(
    business_name: str,
    industries: list,
    trade_type: str,
    annual_turnover: float,
    credit_sales_percentage: float,
    years_in_business: int,
    customer_country: str,
    customer_country_code: str
) -> str:
    """
    Collects and stores core business information from the customer.
    ONLY call this tool after ALL 8 fields below have been collected.
    Do NOT call this tool if any field is missing or has a default value.

    Required fields -- ALL must be provided before calling:
    1. business_name          : name of the business
    2. industries             : list of industry sectors
    3. trade_type             : must be "export", "domestic", or "both"
    4. annual_turnover        : annual turnover in GBP -- must be > 0
    5. credit_sales_percentage: percentage sold on credit -- must be > 0
    6. years_in_business      : years trading -- must be > 0
    7. customer_country       : full country name where business is based
    8. customer_country_code  : 2-letter country code derived from country name

    Returns confirmation of what was collected.
    """
    # Pydantic validation
    is_valid, error, validated = validate_model(BusinessInfo, {
        "business_name":           business_name,
        "industries":              industries,
        "trade_type":              trade_type,
        "annual_turnover":         annual_turnover,
        "credit_sales_percentage": credit_sales_percentage,
        "years_in_business":       years_in_business,
        "customer_country":        customer_country,
        "customer_country_code":   customer_country_code,
    })
    if not is_valid:
        return json.dumps({"error": error})

    session["business_name"]           = validated["business_name"]
    session["industries"]              = validated["industries"]
    session["trade_type"]              = validated["trade_type"]
    session["annual_turnover"]         = validated["annual_turnover"]
    session["credit_sales_percentage"] = validated["credit_sales_percentage"]
    session["years_in_business"]       = validated["years_in_business"]
    session["customer_country"]        = validated["customer_country"]
    session["customer_country_code"]   = validated["customer_country_code"]
    progress = session.get("progress", {})
    progress["business_collected"] = True

    logging.info(f"Business info collected: {business_name} ({customer_country})")

    return json.dumps({
        "status":           "collected",
        "progress":         "1 of 3 -- Business info complete. Next: collect buyer information.",
        "business":         business_name,
        "industry":         industries,
        "trade":            trade_type,
        "turnover":         annual_turnover,
        "customer_country": customer_country,
    })


@tool
def collect_buyer_info(
    buyers: list,
    buyer_countries: list,
    top_buyer_percentage: float,
    payment_terms_days: int,
    loss_ratio: float
) -> str:
    """
    Collects and stores buyer and trading information from the customer.
    ONLY call this tool once Steps 8, 9, 10 and 11 are ALL complete.
    Never call this tool with 0 buyers or missing buyer fields.

    Required fields:
    - buyers: list of buyer objects, each must have:
        - name             : buyer business name
        - country          : buyer country full name
        - country_code     : 2-letter code derived from country name
        - industry         : buyer industry sector
        - exposure_amount  : credit exposure in GBP
        - registration_number: registration number or "UNKNOWN"
    - buyer_countries      : list of all buyer countries
            - top_buyer_percentage : % of total exposure in the largest single buyer
    - payment_terms_days   : standard payment terms in days
    - loss_ratio           : historical bad debt ratio as decimal

    Returns confirmation of what was collected.
    """
    # If set_buyer_count was not called, set it now from buyers list
    if not session.get("declared_buyer_count"):
        session["declared_buyer_count"] = len(buyers)

    # Pydantic validation
    is_valid, error, validated = validate_model(BuyerInfo, {
        "buyers":               buyers,
        "buyer_countries":      buyer_countries,
        "top_buyer_percentage": top_buyer_percentage,
        "payment_terms_days":   payment_terms_days,
        "loss_ratio":           loss_ratio,
        "declared_buyer_count": session.get("declared_buyer_count", len(buyers)),
    })
    if not is_valid:
        return json.dumps({"error": error})

    session["buyers"]               = validated["buyers"]
    session["buyer_countries"]      = validated["buyer_countries"]
    session["top_buyer_percentage"] = validated["top_buyer_percentage"]
    session["payment_terms_days"]   = validated["payment_terms_days"]
    session["loss_ratio"]           = validated["loss_ratio"]
    session["intake_complete"]      = True

    # Validate domestic trade type against customer country
    trade_type           = session.get("trade_type", "")
    customer_country_code = session.get("customer_country_code", "").upper()

    if trade_type == "domestic" and customer_country_code:
        foreign_buyers = [
            b.get("name") for b in buyers
            if b.get("country_code", "").upper() != customer_country_code
        ]
        if foreign_buyers:
            session["intake_complete"] = False
            return json.dumps({
                "error":          "trade_type_mismatch",
                "message":        f"Trade type is domestic but these buyers are not in {session.get('customer_country')}: {foreign_buyers}. Please clarify -- either change trade type to export/both or confirm all buyers are in {session.get('customer_country')}.",
                "foreign_buyers": foreign_buyers
            })

    logging.info(f"Buyer info collected: {len(buyers)} buyers")

    return json.dumps({
        "status":        "collected",
        "buyer_count":   len(buyers),
        "countries":     buyer_countries,
        "payment_terms": payment_terms_days,
    })


@tool
def upload_financial_document(file_path: str) -> str:
    """
    Extracts financial figures automatically from an uploaded
    financial statement document using Nova Multimodal.
    Supports PDF, DOCX, XLSX, CSV, TXT formats.

    Call this tool when the customer provides a file path to
    their financial statement instead of manually entering figures.
    This tool automatically extracts all 11 required financial figures.

    Args:
        file_path: full path to the uploaded financial statement

    Returns:
        extraction result with financial figures or error message
    """
    success, message, financials = process_uploaded_document(file_path)

    if not success:
        return json.dumps({
            "error":   f"Document extraction failed: {message}",
            "action":  "Ask customer to provide financial figures manually instead"
        })

    # Store extracted financials in session
    session["financials"] = financials
    progress = session.get("progress", {})
    progress["financials_collected"] = True

    logging.info(f"Financial document processed successfully")

    return json.dumps({
        "status":    "extracted",
        "progress":  "3 of 3 -- Financial data extracted from document. Ready to run underwriting.",
        "message":   message,
        "financials": financials
    })


@tool
def collect_financial_data(
    annual_revenue: float,
    current_assets: float,
    current_liabilities: float,
    total_liabilities: float,
    tangible_net_worth: float,
    total_assets: float,
    capital: float,
    bad_debts: float,
    debtors: float,
    creditors: float,
    cost_of_sales: float
) -> str:
    """
    Stores financial data from the customer's financial statements.
    ONLY call this tool after the customer has explicitly provided ALL
    11 financial figures. Do NOT call with zero or placeholder values.
    Do NOT call before Step 13 in the conversation flow.

    Required figures (all in GBP):
    1.  annual_revenue
    2.  current_assets
    3.  current_liabilities
    4.  total_liabilities
    5.  tangible_net_worth  -- can be negative
    6.  total_assets
    7.  capital
    8.  bad_debts
    9.  debtors
    10. creditors
    11. cost_of_sales

    Returns confirmation of collection.
    """
    # Pydantic validation
    is_valid, error, validated = validate_model(FinancialData, {
        "annual_revenue":       annual_revenue,
        "current_assets":       current_assets,
        "current_liabilities":  current_liabilities,
        "total_liabilities":    total_liabilities,
        "tangible_net_worth":   tangible_net_worth,
        "total_assets":         total_assets,
        "capital":              capital,
        "bad_debts":            bad_debts,
        "debtors":              debtors,
        "creditors":            creditors,
        "cost_of_sales":        cost_of_sales,
    })
    if not is_valid:
        return json.dumps({"error": error})

    session["financials"] = validated

    progress = session.get("progress", {})
    progress["financials_collected"] = True

    logging.info("Financial data collected")

    return json.dumps({
        "status":   "collected",
        "progress": "3 of 3 -- Financial data complete. Ready to run underwriting.",
        "revenue":  annual_revenue,
        "tnw":      tangible_net_worth,
    })


@tool
def run_underwriting() -> str:
    """
    Runs the underwriting risk scoring engine using all collected data.
    ONLY call this tool after business info, buyer info, AND financial
    data have ALL been collected. Do NOT call if any data is missing.

    Returns the risk score, tier, premium rate, and full breakdown.
    If declined, returns the reason for decline.
    """
    if not session.get("intake_complete"):
        return json.dumps({"error": "Intake not complete -- collect business and buyer info first"})

    # Validate all data before running underwriting
    error = validate_all()
    if error:
        return json.dumps({"error": error})

    profile = {
        "business_name":           session.get("business_name"),
        "industries":              session.get("industries"),
        "trade_type":              session.get("trade_type"),
        "annual_turnover":         session.get("annual_turnover"),
        "credit_sales_percentage": session.get("credit_sales_percentage"),
        "buyer_countries":         session.get("buyer_countries"),
        "top_buyer_percentage":    session.get("top_buyer_percentage"),
        "payment_terms_days":      session.get("payment_terms_days"),
        "loss_ratio":              session.get("loss_ratio"),
        "years_in_business":       session.get("years_in_business"),
        "buyers":                  session.get("buyers"),
        "financials":              session.get("financials"),
    }

    result = calculate_risk_score(profile)
    session["underwriting_result"] = result

    progress = session.get("progress", {})
    progress["underwriting_done"] = True

    logging.info(f"Underwriting complete: {result['risk_tier']} (Score: {result['final_score']})")
    logging.info(f"Underwriting result stored: {session['underwriting_result'] is not None}")

    return json.dumps(result)


@tool
def generate_policy_options() -> str:
    """
    Generates 3 policy coverage options based on the underwriting result.
    ONLY call this tool after run_underwriting has completed successfully.
    Do NOT call if risk tier is Declined.

    Returns 3 policy options with coverage levels and premiums.
    """
    result = session.get("underwriting_result")
    if not result:
        return json.dumps({"error": "Run underwriting first"})

    risk_tier    = result.get("risk_tier", "")
    premium_rate = result.get("premium_rate", "0%")

    if risk_tier == "Declined":
        return json.dumps({"error": "Policy declined -- cannot generate options"})

    turnover     = session.get("annual_turnover", 0)
    credit_pct   = session.get("credit_sales_percentage", 0)
    credit_sales = turnover * (credit_pct / 100)
    base_premium = float(str(premium_rate).split("%")[0])

    options = {
        "option_1": {
            "name":                 "Essential Cover",
            "indemnity_percentage": 75,
            "waiting_period_days":  120,
            "political_risk":       False,
            "single_buyer_cover":   False,
            "premium_rate":         f"{round(base_premium * 0.85, 2)}%",
            "annual_premium":       f"{round(credit_sales * (base_premium * 0.85) / 100, 2):,.2f}",
            "description":          "Basic protection for low-risk trading relationships"
        },
        "option_2": {
            "name":                 "Business Cover",
            "indemnity_percentage": 85,
            "waiting_period_days":  90,
            "political_risk":       True,
            "single_buyer_cover":   False,
            "premium_rate":         f"{round(base_premium, 2)}%",
            "annual_premium":       f"{round(credit_sales * base_premium / 100, 2):,.2f}",
            "description":          "Comprehensive cover with political risk protection"
        },
        "option_3": {
            "name":                 "Premium Cover",
            "indemnity_percentage": 90,
            "waiting_period_days":  60,
            "political_risk":       True,
            "single_buyer_cover":   True,
            "premium_rate":         f"{round(base_premium * 1.20, 2)}%",
            "annual_premium":       f"{round(credit_sales * (base_premium * 1.20) / 100, 2):,.2f}",
            "description":          "Maximum protection including single buyer cover"
        },
    }

    logging.info("Policy options generated")
    return json.dumps(options)


@tool
def issue_policy(selected_option: str) -> str:
    """
    Issues the policy for the selected coverage option and saves to database.
    ONLY call this tool after the customer has confirmed their chosen option.
    Do NOT call if any data is missing or underwriting has not been run.

    Args:
        selected_option: "option_1", "option_2", or "option_3"

    Returns the policy number and confirmation details.
    """
    logging.info(f"issue_policy called with option: {selected_option}")

    # Validate all data before issuing policy
    error = validate_all()
    if error:
        return json.dumps({"error": f"Cannot issue policy -- {error}"})

    result = session.get("underwriting_result")

    # If result missing but intake complete, rerun underwriting
    if not result and session.get("intake_complete"):
        logging.warning("Underwriting result missing -- rerunning")
        rerun      = run_underwriting()
        rerun_data = json.loads(rerun)
        if "error" in rerun_data:
            return json.dumps({"error": f"Underwriting failed: {rerun_data['error']}"})
        result = session.get("underwriting_result")

    if not result:
        return json.dumps({"error": "No underwriting result -- please complete application first"})

    # Save customer to database
    customer_id = save_customer({
        "business_name":   session.get("business_name"),
        "registration_no": "REG-PENDING",
        "industry":        str(session.get("industries", [])),
        "trade_type":      session.get("trade_type"),
        "annual_turnover": session.get("annual_turnover"),
        "country":         session.get("customer_country", "Unknown"),
        "contact_email":   "pending@example.com",
    })

    # Generate policy ID and dates
    policy_id  = generate_policy_id()
    start_date = datetime.now().strftime("%Y-%m-%d")
    end_date   = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")

    # Save buyers
    for buyer in session.get("buyers", []):
        save_buyer({
            "registration_number": buyer.get("registration_number", "UNKNOWN"),
            "country_code":        buyer.get("country_code", "XX"),
            "business_name":       buyer.get("name"),
            "industry":            buyer.get("industry"),
            "status":              "active",
        })

    # Extract result fields safely
    premium_rate_str   = str(result.get("premium_rate", "0%")).split("%")[0]
    annual_premium_str = str(result.get("annual_premium", "0")).replace(",", "")
    final_score        = result.get("final_score", 0)
    risk_tier          = result.get("risk_tier", "Unknown")

    # Save policy to customer record
    add_policy_to_customer(customer_id, {
        "policy_id":           policy_id,
        "status":              "ACTIVE",
        "risk_score":          final_score,
        "risk_tier":           risk_tier,
        "premium_rate":        Decimal(premium_rate_str),
        "annual_premium":      Decimal(annual_premium_str),
        "term_classification": "Short Term",
        "policy_start_date":   start_date,
        "policy_end_date":     end_date,
        "covered_buyers":      [b.get("name") for b in session.get("buyers", [])],
        "selected_option":     selected_option,
        "claims":              [],
    })

    session["customer_id"]                  = customer_id
    session["selected_policy"]              = policy_id
    progress = session.get("progress", {})
    progress["policy_issued"] = True

    logging.info(f"Policy issued: {policy_id} for customer: {customer_id}")

    return json.dumps({
        "status":      "POLICY_ISSUED",
        "policy_id":   policy_id,
        "customer_id": customer_id,
        "start_date":  start_date,
        "end_date":    end_date,
        "risk_tier":   risk_tier,
        "risk_score":  final_score,
    })


# ============================================================
# SECTION 5 -- SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are Alex, a senior Trade Credit Insurance underwriter at TCI Shield.
You have 20 years of experience underwriting trade credit risk for businesses
across the UK and Europe.

YOUR GOAL:
Guide the customer through a complete trade credit insurance application by:
1. Collecting their business information
2. Collecting their buyer information
3. Processing their financial data
4. Running the underwriting assessment
5. Presenting policy options
6. Issuing the selected policy

YOUR APPROACH:
- Be professional, warm, and clear
- Ask ONLY ONE question per response -- this is a strict rule, never ask two questions at once
- Wait for the customer to answer before asking the next question
- Acknowledge what the customer tells you before asking the next question
- Explain insurance terms in plain English
- When you have enough information for a step, call the appropriate tool
- After running underwriting, explain the result clearly to the customer

CONVERSATION FLOW:
Step 1  -- Greet the customer and ask for their business name, industry, and country they are based in
Step 2  -- Ask about trade type (export, domestic, or both). Explain that domestic means all buyers are in the same country as the business.
Step 3  -- Ask about annual turnover in GBP
Step 4  -- Ask about credit sales percentage
Step 5  -- Ask about years in business
Step 6  -- Call collect_business_info tool ONLY after ALL of Steps 1-5 are complete. All 8 fields must be collected: business name, industry, trade type, annual turnover, credit sales percentage, years in business, customer country, AND customer country code. Derive the 2-letter country code yourself from the country name. Never call this tool if any field is missing.
Step 7  -- Ask for the total number of buyers they have
Step 8  -- For EACH buyer, ask for name, country, industry, and credit exposure amount ONE buyer at a time. Derive the 2-letter country code yourself. Never ask the customer for a country code. Do NOT proceed to Step 9 until you have collected details for ALL buyers declared in Step 7.
Step 9  -- Ask about standard payment terms in days
Step 10 -- Ask about the largest single buyer as a percentage of total exposure
Step 11 -- Ask about historical bad debt loss ratio as a decimal
Step 12 -- Call collect_buyer_info tool ONLY after Steps 8, 9, 10 and 11 are ALL complete. The buyers list must contain the same number of buyers declared in Step 7. Never call this tool with 0 buyers.
Step 13 -- Ask customer to provide ALL financial figures in plain numbers. Ask them to provide: annual revenue, current assets, current liabilities, total liabilities, tangible net worth, total assets, capital, bad debts, debtors, creditors, and cost of sales. Do NOT call collect_financial_data until ALL 11 figures have been provided.
Step 14 -- Call collect_financial_data tool immediately with the provided figures. Do NOT wait for user confirmation.
Step 15 -- Immediately call run_underwriting tool right after collect_financial_data completes. Do NOT call run_underwriting if financial data has not been collected. Do NOT wait for user input between these two steps.
Step 16 -- Present the result to the customer in plain language without showing raw scores or JSON
Step 17 -- Use the generate_policy_options tool now. Present all 3 options clearly with name, indemnity percentage, waiting period, political risk, and annual premium. Do NOT ask permission first. Do NOT describe what you are about to do -- just do it.
Step 18 -- Ask customer to select an option by saying option_1, option_2, or option_3
Step 19 -- Call issue_policy with selected option
Step 20 -- Confirm policy issuance using the EXACT policy_id, start_date and end_date returned by the issue_policy tool. Never use placeholders like [Your Policy Number]. Always quote the real policy number from the tool result.

IMPORTANT RULES:
- If trade type is domestic but customer declares buyers in a different country to the customer's own country, flag this inconsistency and ask customer to clarify -- either change trade type to export/both or confirm all buyers are in the same country as the business
- Never proceed with underwriting if trade type and buyer countries are inconsistent
- If unsure what has been collected or what step to take next, call get_progress tool to check current status
- Always check progress before calling any collection tool to avoid duplicate collection
- Never run underwriting before collecting all required information
- Always explain a decline decision clearly and professionally
- Negative TNW means the company is technically insolvent -- handle sensitively
- Keep responses concise -- no more than 3-4 sentences per turn
- Never show raw data, JSON, or technical scores to the customer
- Always present numbers in plain English (e.g. "your risk score is moderate")
"""

# ============================================================
# SECTION 6 -- ORCHESTRATOR AGENT
# ============================================================
# Agent is created fresh inside run_conversation() on each run
# to ensure clean conversation history and session state.

nova_lite_model = BedrockModel(
    model_id=NOVA_LITE_MODEL_ID,
    region_name=AWS_REGION,
)

# ============================================================
# SECTION 7 -- CONVERSATION LOOP
# ============================================================

def reset_session():
    """Resets session state for a new conversation."""
    session.update({
        "customer_id":              None,
        "business_name":            None,
        "industries":               [],
        "trade_type":               None,
        "annual_turnover":          None,
        "credit_sales_percentage":  None,
        "buyer_countries":          [],
        "top_buyer_percentage":     None,
        "payment_terms_days":       None,
        "loss_ratio":               None,
        "years_in_business":        None,
        "buyers":                   [],
        "financials":               None,
        "underwriting_result":      None,
        "selected_policy":          None,
        "intake_complete":          False,
        "customer_country":         None,
        "customer_country_code":    None,
        "declared_buyer_count":     None,
        "progress": {
            "business_collected":   False,
            "buyers_collected":     False,
            "financials_collected": False,
            "underwriting_done":    False,
            "policy_issued":        False,
        }
    })


def run_conversation():
    """Runs an interactive text conversation with the TCI agent."""
    logging.info("TCI Agent started")

    # Reset session and create fresh agent for clean state
    reset_session()
    agent = Agent(
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

    print("\n" + "=" * 60)
    print("TCI Shield -- Trade Credit Insurance Agent")
    print("Type 'quit' to exit")
    print("=" * 60 + "\n")

    response = agent("Hello, I would like to apply for trade credit insurance.")
    print(f"Alex: {extract_text(response)}\n")

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ["quit", "exit", "bye"]:
            print("\nAlex: Thank you for using TCI Shield. Goodbye!")
            break
        if not user_input:
            continue

        print()
        response = agent(user_input)
        print(f"\nAlex: {extract_text(response)}\n")


def run_underwriting_from_transcript(transcript_summary: str, extracted_financials: dict = None) -> dict:
    """
    Called by voice_agent.py after voice conversation ends.
    Processes transcript, runs underwriting, generates policy options.
    Returns policy options dict for Streamlit to display.
    Does NOT issue policy -- Streamlit handles that after customer selects.
    """
    reset_session()
    if extracted_financials:
        session["financials"] = extracted_financials
        session["progress"]["financials_collected"] = True
        logging.info("Pre-extracted financials restored after session reset")

    agent = Agent(
        model=nova_lite,
        system_prompt=SYSTEM_PROMPT + """
        IMPORTANT: You are processing a completed voice conversation transcript.
        Extract ALL information from the transcript and call tools in this exact order:
        1. Call set_buyer_count with the number of buyers
        2. Call collect_business_info with all business details
        3. Call collect_buyer_info with all buyer details
        4. Call collect_financial_data with all financial figures
        5. Call run_underwriting immediately
        6. Call generate_policy_options immediately
        7. STOP after generate_policy_options -- do NOT call issue_policy
        8. Do NOT ask any questions -- just process the transcript
        9. If any data is missing write MISSING_DATA: followed by missing fields
        """,
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

    logging.info("Running underwriting from voice transcript")
    result = agent(transcript_summary)

    result_text = str(result)
    if "MISSING_DATA:" in result_text:
        missing_line = [
            line for line in result_text.split("\n")
            if "MISSING_DATA:" in line
        ]
        if missing_line:
            missing_fields = missing_line[0].replace("MISSING_DATA:", "").strip()
            with open("voice_missing.json", "w") as f:
                json.dump({
                    "missing_fields": missing_fields,
                    "policy_issued":  False
                }, f)
            logging.warning(f"Voice transcript missing: {missing_fields}")
            return {}

    underwriting_result = session.get("underwriting_result")
    if not underwriting_result:
        logging.error("Underwriting result missing after transcript processing")
        return {}

    options_json = generate_policy_options()
    options      = json.loads(options_json)

    if "error" in options:
        logging.error(f"Policy options error: {options['error']}")
        return {}

    logging.info("Voice transcript processed successfully -- options ready")

    return {
        "underwriting_result": underwriting_result,
        "policy_options":      options,
        "session_ready":       True
    }


def issue_policy_from_voice(selected_option: str) -> dict:
    """
    Called by Streamlit after customer selects a policy option
    from the voice agent flow.
    Session state is already populated from run_underwriting_from_transcript.
    """
    result_json = issue_policy(selected_option)
    result      = json.loads(result_json)
    logging.info(f"Policy issued from voice: {result.get('policy_id')}")
    return result

# ============================================================
# SECTION 8 -- ENTRY POINT
# ============================================================

if __name__ == "__main__":
    run_conversation()