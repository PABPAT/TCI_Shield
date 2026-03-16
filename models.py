# ============================================================
# TRADE CREDIT INSURANCE -- PYDANTIC DATA MODELS
# ============================================================
# Defines strict data models for each collection stage.
# Used to validate data before storing in session.
# If any field is missing or wrong type, validation fails
# and a clear error is returned to Nova.
# ============================================================

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional
import logging

# ============================================================
# SECTION 1 -- BUSINESS INFO MODEL
# ============================================================

class BusinessInfo(BaseModel):
    """
    Validates business information collected in Steps 1-5.
    All fields are required -- no optional fields.
    """
    business_name:            str   = Field(..., min_length=1,   description="Name of the business")
    industries:               list  = Field(..., min_length=1,   description="List of industry sectors")
    trade_type:               str   = Field(...,                 description="export, domestic, or both")
    annual_turnover:          float = Field(..., gt=0,           description="Annual turnover in GBP")
    credit_sales_percentage:  float = Field(..., gt=0, le=100,   description="Percentage of turnover sold on credit")
    years_in_business:        int   = Field(..., gt=0,           description="Years the business has been trading")
    customer_country:         str   = Field(..., min_length=2,   description="Country where business is based")
    customer_country_code:    str   = Field(..., min_length=2, max_length=3, description="2-letter country code")

    @field_validator("trade_type")
    @classmethod
    def validate_trade_type(cls, value: str) -> str:
        allowed = ["export", "domestic", "both"]
        if value.lower() not in allowed:
            raise ValueError(f"Trade type must be one of: {allowed}. Got: {value}")
        return value.lower()

    @field_validator("customer_country_code")
    @classmethod
    def validate_country_code(cls, value: str) -> str:
        return value.upper().strip()

    @field_validator("industries")
    @classmethod
    def validate_industries(cls, value: list) -> list:
        if not value or len(value) == 0:
            raise ValueError("At least one industry must be provided")
        return value


# ============================================================
# SECTION 2 -- BUYER MODEL
# ============================================================

class Buyer(BaseModel):
    """
    Validates a single buyer's details.
    All fields required except registration_number.
    """
    name:                str   = Field(..., min_length=1,  description="Buyer business name")
    country:             str   = Field(..., min_length=2,  description="Buyer country full name")
    country_code:        str   = Field(..., min_length=2, max_length=3, description="2-letter country code")
    industry:            str   = Field(..., min_length=2,  description="Buyer industry sector")
    exposure_amount:     float = Field(..., gt=0,          description="Credit exposure in GBP")
    registration_number: str   = Field("UNKNOWN",          description="Company registration number")

    @field_validator("country_code")
    @classmethod
    def validate_country_code(cls, value: str) -> str:
        return value.upper().strip()


# ============================================================
# SECTION 3 -- BUYER INFO MODEL
# ============================================================

class BuyerInfo(BaseModel):
    """
    Validates all buyer and trading information collected in Steps 7-11.
    """
    buyers:               list  = Field(..., min_length=1,        description="List of buyer objects")
    buyer_countries:      list  = Field(..., min_length=1,        description="List of all buyer countries")
    top_buyer_percentage: float = Field(..., gt=0, le=100,        description="% of exposure in largest buyer")
    payment_terms_days:   int   = Field(..., gt=0,                description="Standard payment terms in days")
    loss_ratio:           float = Field(..., ge=0, le=1,          description="Historical bad debt ratio as decimal")
    declared_buyer_count: int   = Field(..., gt=0,                description="Total buyers declared by customer")

    @model_validator(mode="after")
    def validate_buyer_count(self) -> "BuyerInfo":
        if len(self.buyers) != self.declared_buyer_count:
            raise ValueError(
                f"Buyer count mismatch -- declared {self.declared_buyer_count} "
                f"but {len(self.buyers)} provided. Collect all buyers before submitting."
            )
        return self

    @model_validator(mode="after")
    def validate_buyer_objects(self) -> "BuyerInfo":
        validated_buyers = []
        for i, buyer in enumerate(self.buyers, 1):
            if isinstance(buyer, dict):
                try:
                    validated_buyers.append(Buyer(**buyer).model_dump())
                except Exception as e:
                    raise ValueError(f"Buyer {i} validation failed: {e}")
            else:
                validated_buyers.append(buyer)
        self.buyers = validated_buyers
        return self


# ============================================================
# SECTION 4 -- FINANCIAL DATA MODEL
# ============================================================

class FinancialData(BaseModel):
    """
    Validates financial figures extracted from financial statements.
    All 11 figures required. TNW can be negative (insolvency indicator).
    """
    annual_revenue:       float = Field(..., gt=0,   description="Annual revenue in GBP")
    current_assets:       float = Field(..., gt=0,   description="Current assets in GBP")
    current_liabilities:  float = Field(..., gt=0,   description="Current liabilities in GBP")
    total_liabilities:    float = Field(..., gt=0,   description="Total liabilities in GBP")
    tangible_net_worth:   float = Field(...,          description="Tangible net worth -- can be negative")
    total_assets:         float = Field(..., gt=0,   description="Total assets in GBP")
    capital:              float = Field(..., ge=0,   description="Paid up capital in GBP")
    bad_debts:            float = Field(..., ge=0,   description="Bad debts written off in GBP")
    debtors:              float = Field(..., ge=0,   description="Total debtors in GBP")
    creditors:            float = Field(..., ge=0,   description="Total creditors in GBP")
    cost_of_sales:        float = Field(..., gt=0,   description="Cost of sales in GBP")

    @model_validator(mode="after")
    def validate_balance_sheet(self) -> "FinancialData":
        # Basic balance sheet sanity check
        # Total assets should roughly equal total liabilities + TNW
        expected_assets = self.total_liabilities + self.tangible_net_worth
        tolerance       = self.total_assets * 0.10  # 10% tolerance
        if abs(self.total_assets - expected_assets) > tolerance:
            logging.warning(
                f"Balance sheet may be inconsistent: "
                f"Total Assets={self.total_assets}, "
                f"Liabilities + TNW={expected_assets}"
            )
        return self


# ============================================================
# SECTION 5 -- VALIDATION HELPER
# ============================================================

def validate_model(model_class, data: dict) -> tuple[bool, str, dict]:
    """
    Validates data against a Pydantic model.

    Args:
        model_class : Pydantic model class to validate against
        data        : dict of data to validate

    Returns:
        tuple of (is_valid, error_message, validated_data)
        - is_valid       : True if validation passed
        - error_message  : empty string if valid, error details if invalid
        - validated_data : validated and cleaned data dict if valid, else empty
    """
    try:
        validated = model_class(**data)
        return True, "", validated.model_dump()
    except Exception as e:
        # Extract clean error messages from Pydantic ValidationError
        errors = []
        if hasattr(e, "errors"):
            for err in e.errors():
                field   = " -> ".join(str(f) for f in err.get("loc", []))
                message = err.get("msg", "Invalid value")
                errors.append(f"{field}: {message}")
        else:
            errors.append(str(e))
        return False, f"Validation failed: {'; '.join(errors)}", {}