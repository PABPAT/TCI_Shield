# ============================================================
# TRADE CREDIT INSURANCE -- DOCUMENT EXTRACTOR
# ============================================================
# Uses Amazon Nova Lite multimodal capability to extract
# financial figures from uploaded financial statements.
#
# Supported formats: PDF, DOCX, XLSX, CSV, TXT
# Nova reads the document and extracts the 11 required
# financial figures automatically -- no manual entry needed.
#
# API used: Bedrock Converse API with document input
# ============================================================

import boto3
import json
import logging
from pathlib import Path
from models import FinancialData, validate_model
from config import NOVA_LITE_MODEL_ID, AWS_REGION

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

# ============================================================
# SECTION 1 -- BEDROCK CLIENT
# ============================================================

client = boto3.client("bedrock-runtime", region_name=AWS_REGION)

# ============================================================
# SECTION 2 -- SUPPORTED FORMATS
# ============================================================

SUPPORTED_FORMATS = {
    ".pdf":  "pdf",
    ".docx": "docx",
    ".xlsx": "xlsx",
    ".csv":  "csv",
    ".txt":  "txt",
    ".html": "html",
    ".md":   "md",
}

# ============================================================
# SECTION 3 -- EXTRACTION PROMPT
# ============================================================
# This prompt tells Nova exactly what to extract and in what
# format. Asking for JSON output makes parsing reliable.

EXTRACTION_PROMPT = """
You are a financial data extraction specialist.
Carefully read the uploaded financial statement and extract
the following figures. Return ONLY a valid JSON object with
exactly these keys and numeric values. Do not include any
explanation, markdown, or text outside the JSON object.

Required fields:
- annual_revenue        : Total revenue / turnover for the year
- current_assets        : Total current assets
- current_liabilities   : Total current liabilities
- total_liabilities     : Total liabilities (current + non-current)
- tangible_net_worth    : Tangible net worth (total equity minus intangibles) -- can be negative
- total_assets          : Total assets
- capital               : Paid up share capital / equity capital
- bad_debts             : Bad debts written off during the year
- debtors               : Total trade debtors / accounts receivable
- creditors             : Total trade creditors / accounts payable
- cost_of_sales         : Cost of goods sold / cost of sales

Rules:
- All values must be numeric (float or int) -- no currency symbols
- If a figure cannot be found, use 0
- If tangible_net_worth is negative, return the negative value
- Use the most recent year's figures if multiple years are shown
- Do not round -- use exact figures from the document

Return format example:
{
    "annual_revenue":       5000000,
    "current_assets":       800000,
    "current_liabilities":  350000,
    "total_liabilities":    1200000,
    "tangible_net_worth":   600000,
    "total_assets":         1800000,
    "capital":              400000,
    "bad_debts":            32000,
    "debtors":              450000,
    "creditors":            280000,
    "cost_of_sales":        2400000
}
"""

# ============================================================
# SECTION 4 -- DOCUMENT READER
# ============================================================

def read_document(file_path: str) -> tuple[bytes, str]:
    """
    Reads a document file and returns bytes and format string.

    Args:
        file_path: path to the document file

    Returns:
        tuple of (file_bytes, format_string)
    """
    path       = Path(file_path)
    extension  = path.suffix.lower()
    doc_format = SUPPORTED_FORMATS.get(extension)

    if not doc_format:
        raise ValueError(
            f"Unsupported file format: {extension}. "
            f"Supported: {list(SUPPORTED_FORMATS.keys())}"
        )

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(path, "rb") as f:
        file_bytes = f.read()

    logging.info(f"Document read: {path.name} ({len(file_bytes)} bytes, format: {doc_format})")
    return file_bytes, doc_format


# ============================================================
# SECTION 5 -- NOVA MULTIMODAL EXTRACTION
# ============================================================

def extract_financials_from_document(file_path: str) -> dict:
    """
    Extracts financial figures from an uploaded document using
    Amazon Nova Lite multimodal capability.

    Args:
        file_path: path to the financial statement document

    Returns:
        dict with extracted financial figures and validation status:
        {
            "success":    True/False,
            "financials": {extracted figures} or {},
            "error":      error message if failed,
            "raw_response": Nova's raw text response
        }
    """
    # Read document
    try:
        doc_bytes, doc_format = read_document(file_path)
    except (ValueError, FileNotFoundError) as e:
        return {"success": False, "financials": {}, "error": str(e), "raw_response": ""}

    # Build Converse API request with document
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "document": {
                        "format": doc_format,
                        "name":   "financial_statement",
                        "source": {
                            "bytes": doc_bytes
                        }
                    }
                },
                {
                    "text": EXTRACTION_PROMPT
                }
            ]
        }
    ]

    # Call Nova Lite via Converse API
    try:
        logging.info(f"Sending document to Nova Lite for extraction...")
        response = client.converse(
            modelId=NOVA_LITE_MODEL_ID,
            messages=messages,
            inferenceConfig={
                "maxTokens":   1000,
                "temperature": 0.1,   # low temperature for consistent extraction
                "topP":        0.1,
            }
        )

        # Extract text response
        raw_text = response["output"]["message"]["content"][0]["text"]
        logging.info(f"Nova response received: {len(raw_text)} characters")

    except Exception as e:
        logging.error(f"Nova API call failed: {e}")
        return {"success": False, "financials": {}, "error": f"API error: {e}", "raw_response": ""}

    # Parse JSON from response
    try:
        # Strip any markdown code blocks if present
        clean_text = raw_text.strip()
        if clean_text.startswith("```"):
            lines      = clean_text.split("\n")
            clean_text = "\n".join(lines[1:-1])

        financials = json.loads(clean_text)
        logging.info(f"JSON parsed successfully: {len(financials)} fields extracted")

    except json.JSONDecodeError as e:
        logging.error(f"JSON parsing failed: {e}")
        logging.error(f"Raw response: {raw_text}")
        return {
            "success":      False,
            "financials":   {},
            "error":        f"Could not parse financial figures from document. Nova response: {raw_text[:200]}",
            "raw_response": raw_text
        }

    # Validate extracted data with Pydantic
    is_valid, error, validated = validate_model(FinancialData, financials)
    if not is_valid:
        logging.warning(f"Extracted data failed validation: {error}")
        return {
            "success":      False,
            "financials":   financials,
            "error":        f"Extracted data validation failed: {error}",
            "raw_response": raw_text
        }

    logging.info("Financial extraction and validation successful")
    return {
        "success":      True,
        "financials":   validated,
        "error":        "",
        "raw_response": raw_text
    }


# ============================================================
# SECTION 6 -- CONVENIENCE FUNCTION FOR AGENT
# ============================================================

def process_uploaded_document(document_path: str) -> tuple[bool, str, dict]:
    """
    Convenience function for use in tci_agent.py.
    Extracts financials and returns clean tuple.

    Args:
        document_path: path to uploaded financial statement

    Returns:
        tuple of (success, message, financials_dict)
    """
    result = extract_financials_from_document(document_path)

    if result["success"]:
        extracted        = result["financials"]
        success_message  = (
            f"Successfully extracted financial figures: "
            f"Revenue £{extracted.get('annual_revenue', 0):,.0f}, "
            f"TNW £{extracted.get('tangible_net_worth', 0):,.0f}, "
            f"Total Assets £{extracted.get('total_assets', 0):,.0f}"
        )
        logging.info(success_message)
        return True, success_message, extracted
    else:
        error_message = result["error"]
        logging.error(f"Extraction failed: {error_message}")
        return False, error_message, {}


# ============================================================
# SECTION 7 -- TEST
# ============================================================

if __name__ == "__main__":

    import sys
    import time

    if len(sys.argv) < 2:
        logging.info("Usage: python document_extractor.py <path_to_financial_statement>")
        logging.info("Example: python document_extractor.py financials.pdf")
        logging.info("")
        logging.info("Supported formats: PDF, DOCX, XLSX, CSV, TXT")
    else:
        test_file_path = sys.argv[1]
        logging.info(f"Processing: {test_file_path}")

        start                                    = time.time()
        success, message, test_financials        = process_uploaded_document(test_file_path)
        elapsed                                  = time.time() - start

        if success:
            logging.info("Extraction successful!")
            logging.info(message)
            logging.info(f"Extraction time: {elapsed:.2f} seconds")
            logging.info("Extracted figures:")
            for field, value in test_financials.items():
                logging.info(f"  {field:<25} : {value:,.2f}")
        else:
            logging.error(f"Extraction failed: {message}")