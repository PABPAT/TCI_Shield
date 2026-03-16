# ============================================================
# TRADE CREDIT INSURANCE -- DATABASE MODULE
# ============================================================
# 2 Tables:
#   1. tci_customers -- customer profile + policy + claims
#   2. tci_buyers    -- buyer info + our experience
#
# ID Formats:
#   Customer : CUST-{sequential, rolls over}    e.g. CUST-0001
#   Policy   : POL-{YEAR}-{4 digit seq}         e.g. POL-2026-0001
#   Claim    : CLM-{YEAR}-{4 digit seq}         e.g. CLM-2026-0001
#   Buyer    : REG-{CC}-{registration_number}   e.g. REG-GB-12345678
# ============================================================

import boto3
import json
import logging
from datetime import datetime
from decimal import Decimal
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

# ============================================================
# CONNECTION
# ============================================================

dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
client   = boto3.client("dynamodb",   region_name="us-east-1")

# ============================================================
# TABLE DEFINITIONS
# ============================================================
# tci_customers fields:
#   customer_id      : CUST-0001
#   business_name    : BuildRight UK Ltd
#   registration_no  : REG-GB-12345678
#   industry         : construction
#   trade_type       : export
#   annual_turnover  : 5000000
#   country          : United Kingdom
#   contact_email    : john@buildright.co.uk
#   policies         : list of policy objects
#   created_at       : 2026-02-21T10:00:00
#   updated_at       : 2026-02-21T10:00:00
#
# Each policy object:
#   policy_id            : POL-2026-0001
#   status               : ACTIVE / EXPIRED / CANCELLED / DECLINED
#   risk_score           : 45
#   risk_tier            : Enhanced
#   premium_rate         : 1.75
#   annual_premium       : 35000.00
#   term_classification  : Short Term
#   policy_start_date    : 2026-03-01
#   policy_end_date      : 2027-03-01
#   covered_buyers       : [buyer_ids]
#   claims               : list of claim objects
#
# Each claim object:
#   claim_id       : CLM-2026-0001
#   buyer_id       : REG-FR-87654321
#   invoice_amount : 50000.00
#   claimed_amount : 42500.00
#   status         : PENDING / APPROVED / REJECTED / PAID
#   reason         : INSOLVENCY / PROTRACTED_DEFAULT
#   claim_date     : 2026-06-01
#
# tci_buyers fields:
#   buyer_id          : REG-FR-87654321
#   registration_no   : 87654321
#   country_code      : FR
#   business_name     : AcmeCorp France SAS
#   industry          : manufacturing
#   sic_code          : 2599
#   status            : active / dissolved / unknown
#   incorporation_date: 2005-06-15
#   total_claims      : 1
#   total_claims_paid : 42500.00
#   risk_flag         : None / WATCH / HIGH_RISK
#   api_data          : raw data from Companies House
#   created_at        : 2026-02-21T10:00:00
#   updated_at        : 2026-02-21T10:00:00


# ============================================================
# SECTION 1 -- TABLE CREATION
# ============================================================

def create_tables():
    """Creates both DynamoDB tables if they do not already exist."""
    tables = [
        {
            "TableName": "tci_customers",
            "KeySchema": [{"AttributeName": "customer_id", "KeyType": "HASH"}],
            "AttributeDefinitions": [{"AttributeName": "customer_id", "AttributeType": "S"}],
            "BillingMode": "PAY_PER_REQUEST"
        },
        {
            "TableName": "tci_buyers",
            "KeySchema": [{"AttributeName": "buyer_id", "KeyType": "HASH"}],
            "AttributeDefinitions": [{"AttributeName": "buyer_id", "AttributeType": "S"}],
            "BillingMode": "PAY_PER_REQUEST"
        }
    ]

    for t in tables:
        try:
            client.describe_table(TableName=t["TableName"])
            logging.info(f"Table exists    : {t['TableName']}")
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                logging.info(f"Creating table  : {t['TableName']}")
                dynamodb.create_table(**t)
                client.get_waiter("table_exists").wait(TableName=t["TableName"])
                logging.info(f"Table created   : {t['TableName']}")


# ============================================================
# SECTION 2 -- ID GENERATORS
# ============================================================

def generate_customer_id() -> str:
    """Generates next sequential customer ID. Rolls over naturally."""
    table = dynamodb.Table("tci_customers")
    try:
        response = table.scan(ProjectionExpression="customer_id")
        items    = response.get("Items", [])
        if not items:
            return "CUST-0001"
        numbers = [
            int(i["customer_id"].replace("CUST-", ""))
            for i in items
            if i["customer_id"].replace("CUST-", "").isdigit()
        ]
        return f"CUST-{str(max(numbers) + 1).zfill(4)}"
    except ClientError:
        return "CUST-0001"


def generate_policy_id() -> str:
    """Generates next sequential policy ID for current year."""
    year  = datetime.now().year
    table = dynamodb.Table("tci_customers")
    try:
        response       = table.scan(ProjectionExpression="policies")
        all_policy_ids = []
        for item in response.get("Items", []):
            for policy in item.get("policies", []):
                pid = policy.get("policy_id", "")
                if pid.startswith(f"POL-{year}-"):
                    all_policy_ids.append(int(pid.split("-")[-1]))
        next_num = max(all_policy_ids) + 1 if all_policy_ids else 1
        return f"POL-{year}-{str(next_num).zfill(4)}"
    except ClientError:
        return f"POL-{year}-0001"


def generate_claim_id() -> str:
    """Generates next sequential claim ID for current year."""
    year  = datetime.now().year
    table = dynamodb.Table("tci_customers")
    try:
        response      = table.scan(ProjectionExpression="policies")
        all_claim_ids = []
        for item in response.get("Items", []):
            for policy in item.get("policies", []):
                for claim in policy.get("claims", []):
                    cid = claim.get("claim_id", "")
                    if cid.startswith(f"CLM-{year}-"):
                        all_claim_ids.append(int(cid.split("-")[-1]))
        next_num = max(all_claim_ids) + 1 if all_claim_ids else 1
        return f"CLM-{year}-{str(next_num).zfill(4)}"
    except ClientError:
        return f"CLM-{year}-0001"


def generate_buyer_id(country_code: str, registration_number: str) -> str:
    """Generates buyer ID from country code and registration number."""
    return f"REG-{country_code.upper().strip()}-{registration_number.strip()}"


# ============================================================
# SECTION 3 -- CUSTOMER OPERATIONS
# ============================================================

def save_customer(data: dict) -> str:
    """Saves a new customer. Returns customer_id."""
    table       = dynamodb.Table("tci_customers")
    customer_id = generate_customer_id()
    now         = datetime.now().isoformat()

    table.put_item(Item={
        "customer_id":     customer_id,
        "business_name":   data.get("business_name"),
        "registration_no": data.get("registration_no"),
        "industry":        data.get("industry"),
        "trade_type":      data.get("trade_type"),
        "annual_turnover": Decimal(str(data.get("annual_turnover", 0))),
        "country":         data.get("country"),
        "contact_email":   data.get("contact_email"),
        "policies":        [],
        "created_at":      now,
        "updated_at":      now,
    })
    logging.info(f"Customer saved  : {customer_id}")
    return customer_id


def get_customer(customer_id: str) -> dict:
    """Retrieves a customer by ID."""
    table    = dynamodb.Table("tci_customers")
    response = table.get_item(Key={"customer_id": customer_id})
    return response.get("Item")


def add_policy_to_customer(customer_id: str, policy: dict):
    """Adds a policy object to a customer's policies list."""
    table = dynamodb.Table("tci_customers")
    table.update_item(
        Key={"customer_id": customer_id},
        UpdateExpression="SET policies = list_append(policies, :p), updated_at = :now",
        ExpressionAttributeValues={
            ":p":   [policy],
            ":now": datetime.now().isoformat()
        }
    )
    logging.info(f"Policy added    : {policy.get('policy_id')} to {customer_id}")


def add_claim_to_policy(customer_id: str, policy_id: str, claim: dict):
    """Adds a claim to a specific policy within a customer record."""
    customer = get_customer(customer_id)
    if not customer:
        logging.warning(f"Customer not found: {customer_id}")
        return

    policies = customer.get("policies", [])
    for i, policy in enumerate(policies):
        if policy.get("policy_id") == policy_id:
            policies[i].setdefault("claims", []).append(claim)
            break

    table = dynamodb.Table("tci_customers")
    table.update_item(
        Key={"customer_id": customer_id},
        UpdateExpression="SET policies = :p, updated_at = :now",
        ExpressionAttributeValues={
            ":p":   policies,
            ":now": datetime.now().isoformat()
        }
    )
    logging.info(f"Claim added     : {claim.get('claim_id')} to {policy_id}")


# ============================================================
# SECTION 4 -- BUYER OPERATIONS
# ============================================================

def save_buyer(data: dict) -> str:
    """Saves a new buyer. Returns buyer_id."""
    table    = dynamodb.Table("tci_buyers")
    buyer_id = generate_buyer_id(
        data.get("country_code", "XX"),
        data.get("registration_number", data.get("registration_no", "UNKNOWN"))
    )
    now = datetime.now().isoformat()

    table.put_item(Item={
        "buyer_id":           buyer_id,
        "registration_no":    data.get("registration_no"),
        "country_code":       data.get("country_code"),
        "business_name":      data.get("business_name"),
        "industry":           data.get("industry"),
        "sic_code":           data.get("sic_code"),
        "status":             data.get("status", "unknown"),
        "incorporation_date": data.get("incorporation_date"),
        "total_claims":       0,
        "total_claims_paid":  Decimal("0"),
        "risk_flag":          None,
        "api_data":           json.dumps(data.get("api_data", {})),
        "created_at":         now,
        "updated_at":         now,
    })
    logging.info(f"Buyer saved     : {buyer_id}")
    return buyer_id


def get_buyer(buyer_id: str) -> dict:
    """Retrieves a buyer by ID."""
    table    = dynamodb.Table("tci_buyers")
    response = table.get_item(Key={"buyer_id": buyer_id})
    return response.get("Item")


def get_buyer_experience(buyer_id: str) -> dict:
    """
    Returns our experience with a specific buyer.
    Logic for how this influences scoring to be defined later.
    """
    buyer = get_buyer(buyer_id)
    if not buyer:
        return {
            "experience":        "NEW_BUYER",
            "total_claims":      0,
            "total_claims_paid": 0,
            "risk_flag":         None
        }
    return {
        "experience":        "KNOWN_BUYER",
        "total_claims":      buyer.get("total_claims", 0),
        "total_claims_paid": float(buyer.get("total_claims_paid", 0)),
        "risk_flag":         buyer.get("risk_flag"),
    }


# ============================================================
# SECTION 5 -- TEST
# ============================================================

if __name__ == "__main__":

    logging.info("Database setup and test started")

    # Create tables
    create_tables()

    # Save customer
    cust_id = save_customer({
        "business_name":   "BuildRight UK Ltd",
        "registration_no": "REG-GB-12345678",
        "industry":        "construction",
        "trade_type":      "export",
        "annual_turnover": 5000000,
        "country":         "United Kingdom",
        "contact_email":   "john@buildright.co.uk",
    })

    # Save buyer
    test_buyer_id = save_buyer({
        "registration_number":  "87654321",
        "country_code":         "FR",
        "business_name":        "AcmeCorp France SAS",
        "industry":             "manufacturing",
        "sic_code":             "2599",
        "status":               "active",
        "incorporation_date":   "2005-06-15",
        "api_data":             {"source": "Companies House", "verified": True}
    })

    # Add policy to customer
    test_policy_id = generate_policy_id()
    add_policy_to_customer(cust_id, {
        "policy_id":           test_policy_id,
        "status":              "ACTIVE",
        "risk_score":          45,
        "risk_tier":           "Enhanced",
        "premium_rate":        Decimal("1.75"),
        "annual_premium":      Decimal("35000"),
        "term_classification": "Short Term",
        "policy_start_date":   "2026-03-01",
        "policy_end_date":     "2027-03-01",
        "covered_buyers":      [test_buyer_id],
        "claims":              []
    })

    # Add claim to policy
    test_claim_id = generate_claim_id()
    add_claim_to_policy(cust_id, test_policy_id, {
        "claim_id":       test_claim_id,
        "buyer_id":       test_buyer_id,
        "invoice_amount": Decimal("50000"),
        "claimed_amount": Decimal("42500"),
        "status":         "PENDING",
        "reason":         "PROTRACTED_DEFAULT",
        "claim_date":     "2026-06-01"
    })

    # Verify all records
    test_customer = get_customer(cust_id)
    test_buyer    = get_buyer(test_buyer_id)
    exp           = get_buyer_experience(test_buyer_id)

    logging.info(f"Customer : {test_customer['business_name']} | Policies: {len(test_customer['policies'])}")
    logging.info(f"Policy   : {test_customer['policies'][0]['policy_id']} | Tier: {test_customer['policies'][0]['risk_tier']}")
    logging.info(f"Claim    : {test_customer['policies'][0]['claims'][0]['claim_id']} | Status: {test_customer['policies'][0]['claims'][0]['status']}")
    logging.info(f"Buyer    : {test_buyer['business_name']} | Status: {test_buyer['status']}")
    logging.info(f"Exp      : {exp['experience']} | Claims: {exp['total_claims']}")
    logging.info("All database operations complete")