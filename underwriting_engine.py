# ============================================================
# TRADE CREDIT INSURANCE -- UNDERWRITING RULES ENGINE
# ============================================================
# Final Score = (Business Profile x 0.30)
#             + (Financial Ratios  x 0.40)
#             + (Buyer Portfolio   x 0.30)
#
# Each stream scored 0-100, weighted, then combined.
# Decline threshold: Final Score >= 75
# Auto decline: Negative TNW
#
# Buyer Risk = (Country Risk x 0.40)
#            + (Industry Risk x 0.40)
#            + (Customer Risk x 0.20)
# ============================================================

import math
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

# ============================================================
# SECTION 1 -- RISK REFERENCE DATA
# ============================================================

# Industry sectors -- risk score and off-cover limit
# Off-cover limit = 75 - industry score (riskier = lower tolerance)
# Score 5 industries get limit of 75 (hardest to breach)
INDUSTRY_RISK = {
    "construction":  {"score": 25, "off_cover_limit": 75 - 25},  # 50
    "retail":        {"score": 20, "off_cover_limit": 75 - 20},  # 55
    "hospitality":   {"score": 20, "off_cover_limit": 75 - 20},  # 55
    "transportation":{"score": 15, "off_cover_limit": 75 - 15},  # 60
    "manufacturing": {"score": 10, "off_cover_limit": 75 - 10},  # 65
    "wholesale":     {"score": 10, "off_cover_limit": 75 - 10},  # 65
    "technology":    {"score":  5, "off_cover_limit": 75 -  0},  # 75
    "professional":  {"score":  5, "off_cover_limit": 75 -  0},  # 75
    "food_beverage": {"score": 15, "off_cover_limit": 75 - 15},  # 60
    "healthcare":    {"score":  5, "off_cover_limit": 75 -  0},  # 75
    "other":         {"score": 15, "off_cover_limit": 75 - 15},  # 60
}

# Trade type risk
TRADE_TYPE_RISK = {
    "export":   7,
    "domestic": 4,
    "both":     6,
}

# Rating to Score conversion
# ---------------------------------------------------------------
# Formula: ceil(base_value + (base_value * pos * factor) + (factor * pos))
#   base_value = 2
#   factor     = 0.75
#   pos        = slab position (A1=0, A2=1, B1=2, B2=3, C1=4, C2=5, D=6)
#
# C Group additional: + (0.5 * no. of C slabs at or below rating)
#   C1 = +0.5 * 1 = 0.5
#   C2 = +0.5 * 2 = 1.0
#
# D Group additional: + 1.5
#
# Examples:
#   A1: ceil(2)                                          = 2
#   A2: ceil(2 + 2*1*0.75 + 0.75*1)                     = ceil(4.25)  = 5
#   B1: ceil(2 + 2*2*0.75 + 0.75*2)                     = ceil(6.50)  = 7
#   B2: ceil(2 + 2*3*0.75 + 0.75*3)                     = ceil(8.75)  = 9
#   C1: ceil(2 + 2*4*0.75 + 0.75*4 + 0.5*1)             = ceil(11.50) = 12
#   C2: ceil(2 + 2*5*0.75 + 0.75*5 + 0.5*2)             = ceil(14.75) = 15
#   D:  ceil(2 + 2*6*0.75 + 0.75*6 + 0.5*2 + 1.5)       = ceil(18.00) = 18
# ---------------------------------------------------------------
RATING_TO_SCORE = {
    "A1":  2,
    "A2":  5,
    "B1":  7,
    "B2":  9,
    "C1": 12,
    "C2": 15,
    "D":  18,
}

# Country risk ratings
COUNTRY_RISK = {
    # A1 -- Insignificant Risk
    "american samoa":               "A1",
    "anguilla":                     "A1",
    "aruba":                        "A1",
    "australia":                    "A1",
    "austria":                      "A1",
    "bermuda":                      "A1",
    "bonaire":                      "A1",
    "british pacific islands":      "A1",
    "british virgin islands":       "A1",
    "cayman islands":               "A1",
    "channel isles":                "A1",
    "christmas island":             "A1",
    "cocos island":                 "A1",
    "cook islands":                 "A1",
    "curacao":                      "A1",
    "czech republic":               "A1",
    "estonia":                      "A1",
    "falkland islands":             "A1",
    "germany":                      "A1",
    "gibraltar":                    "A1",
    "guam":                         "A1",
    "heard island":                 "A1",
    "iceland":                      "A1",
    "india":                        "A1",
    "italy":                        "A1",
    "japan":                        "A1",
    "montserrat":                   "A1",
    "netherlands":                  "A1",
    "new zealand":                  "A1",
    "niue island":                  "A1",
    "norfolk island":               "A1",
    "northern mariana islands":     "A1",
    "norway":                       "A1",
    "palau":                        "A1",
    "puerto rico":                  "A1",
    "san marino":                   "A1",
    "singapore":                    "A1",
    "sint maarten":                 "A1",
    "south korea":                  "A1",
    "st. helena":                   "A1",
    "sweden":                       "A1",
    "switzerland":                  "A1",
    "tokelau":                      "A1",
    "turks and caicos islands":     "A1",
    "united kingdom":               "A1",
    "uk":                           "A1",
    "united states":                "A1",
    "usa":                          "A1",
    "us minor outlying islands":    "A1",
    "us virgin islands":            "A1",

    # A2 -- Low Risk
    "andorra":                      "A2",
    "bahrain":                      "A2",
    "belgium":                      "A2",
    "bhutan":                       "A2",
    "botswana":                     "A2",
    "brazil":                       "A2",
    "bulgaria":                     "A2",
    "canada":                       "A2",
    "canary islands":               "A2",
    "croatia":                      "A2",
    "cyprus":                       "A2",
    "denmark":                      "A2",
    "faroe islands":                "A2",
    "finland":                      "A2",
    "france":                       "A2",
    "french guiana":                "A2",
    "french polynesia":             "A2",
    "greenland":                    "A2",
    "guadeloupe":                   "A2",
    "guyana":                       "A2",
    "indonesia":                    "A2",
    "ireland":                      "A2",
    "kuwait":                       "A2",
    "latvia":                       "A2",
    "liechtenstein":                "A2",
    "lithuania":                    "A2",
    "luxembourg":                   "A2",
    "malaysia":                     "A2",
    "malta":                        "A2",
    "martinique":                   "A2",
    "mauritius":                    "A2",
    "mayotte":                      "A2",
    "mexico":                       "A2",
    "monaco":                       "A2",
    "new caledonia":                "A2",
    "oman":                         "A2",
    "philippines":                  "A2",
    "poland":                       "A2",
    "portugal":                     "A2",
    "qatar":                        "A2",
    "reunion islands":              "A2",
    "romania":                      "A2",
    "saudi arabia":                 "A2",
    "slovakia":                     "A2",
    "slovenia":                     "A2",
    "spain":                        "A2",
    "st. pierre and miquelon":      "A2",
    "thailand":                     "A2",
    "united arab emirates":         "A2",
    "uae":                          "A2",
    "uruguay":                      "A2",
    "vatican city":                 "A2",
    "wallis and futuna":            "A2",

    # B1 -- Moderately Low Risk
    "albania":                      "B1",
    "algeria":                      "B1",
    "angola":                       "B1",
    "azerbaijan":                   "B1",
    "bahamas":                      "B1",
    "belize":                       "B1",
    "brunei":                       "B1",
    "cambodia":                     "B1",
    "chile":                        "B1",
    "china":                        "B1",
    "colombia":                     "B1",
    "cote divoire":                 "B1",
    "cuba":                         "B1",
    "dominican republic":           "B1",
    "ecuador":                      "B1",
    "fiji":                         "B1",
    "georgia":                      "B1",
    "guatemala":                    "B1",
    "hong kong":                    "B1",
    "hungary":                      "B1",
    "jamaica":                      "B1",
    "kazakhstan":                   "B1",
    "macao":                        "B1",
    "nauru":                        "B1",
    "nepal":                        "B1",
    "paraguay":                     "B1",
    "peru":                         "B1",
    "st. christopher and nevis":    "B1",
    "st. lucia":                    "B1",
    "south africa":                 "B1",
    "serbia":                       "B1",
    "seychelles":                   "B1",
    "timor leste":                  "B1",
    "trinidad and tobago":          "B1",
    "vanuatu":                      "B1",
    "vietnam":                      "B1",

    # B2 -- Moderate Risk
    "armenia":                      "B2",
    "bangladesh":                   "B2",
    "barbados":                     "B2",
    "belarus":                      "B2",
    "benin":                        "B2",
    "bosnia and herzegovina":       "B2",
    "cape verde":                   "B2",
    "costa rica":                   "B2",
    "greece":                       "B2",
    "honduras":                     "B2",
    "israel":                       "B2",
    "jordan":                       "B2",
    "kyrgyzstan":                   "B2",
    "madagascar":                   "B2",
    "montenegro":                   "B2",
    "morocco":                      "B2",
    "namibia":                      "B2",
    "nicaragua":                    "B2",
    "nigeria":                      "B2",
    "north macedonia":              "B2",
    "panama":                       "B2",
    "rwanda":                       "B2",
    "senegal":                      "B2",
    "solomon islands":              "B2",
    "st. vincent":                  "B2",
    "taiwan":                       "B2",
    "tanzania":                     "B2",
    "togo":                         "B2",
    "turkey":                       "B2",
    "turkmenistan":                 "B2",
    "uganda":                       "B2",
    "uzbekistan":                   "B2",

    # C1 -- Moderately High Risk
    "antigua and barbuda":          "C1",
    "argentina":                    "C1",
    "bolivia":                      "C1",
    "comoros":                      "C1",
    "democratic republic of congo": "C1",
    "dominica":                     "C1",
    "egypt":                        "C1",
    "equatorial guinea":            "C1",
    "gambia":                       "C1",
    "kenya":                        "C1",
    "kiribati":                     "C1",
    "lesotho":                      "C1",
    "liberia":                      "C1",
    "maldives":                     "C1",
    "moldova":                      "C1",
    "mongolia":                     "C1",
    "mauritania":                   "C1",
    "samoa":                        "C1",
    "tonga":                        "C1",

    # C2 -- High Risk
    "burkina faso":                 "C2",
    "cameroon":                     "C2",
    "chad":                         "C2",
    "djibouti":                     "C2",
    "eswatini":                     "C2",
    "gabon":                        "C2",
    "ghana":                        "C2",
    "guinea":                       "C2",
    "iran":                         "C2",
    "iraq":                         "C2",
    "laos":                         "C2",
    "libya":                        "C2",
    "marshall islands":             "C2",
    "niger":                        "C2",
    "papua new guinea":             "C2",
    "russia":                       "C2",
    "sierra leone":                 "C2",
    "syria":                        "C2",
    "tajikistan":                   "C2",
    "tuvalu":                       "C2",
    "ukraine":                      "C2",

    # D -- Very High Risk
    "afghanistan":                  "D",
    "burundi":                      "D",
    "central african republic":     "D",
    "congo republic":               "D",
    "el salvador":                  "D",
    "eritrea":                      "D",
    "ethiopia":                     "D",
    "guinea bissau":                "D",
    "haiti":                        "D",
    "lebanon":                      "D",
    "malawi":                       "D",
    "mali":                         "D",
    "micronesia":                   "D",
    "mozambique":                   "D",
    "myanmar":                      "D",
    "north korea":                  "D",
    "pakistan":                     "D",
    "palestine":                    "D",
    "sao tome":                     "D",
    "somalia":                      "D",
    "south sudan":                  "D",
    "sri lanka":                    "D",
    "sudan":                        "D",
    "suriname":                     "D",
    "tunisia":                      "D",
    "venezuela":                    "D",
    "yemen":                        "D",
    "zambia":                       "D",
    "zimbabwe":                     "D",

    "other": "B2",
}

# Payment terms risk (Short Term -- up to 360 days)
# 361 days and above = Medium-Long Term
# 1460 days and above = Long Term
PAYMENT_TERMS_RISK = {
    (0,   30):   0,
    (31,  60):   5,
    (61,  90):  10,
    (91, 120):  15,
    (121, 360): 20,
}

LONG_TERM_PAYMENT_RISK = {
    (361,  1459):  20,
    (1460, 99999): 40,
}

# Base premium range (% of credit sales volume)
PREMIUM_RANGE = {
    "Standard":         {"min": 1.00, "max": 1.75},
    "Enhanced":         {"min": 1.75, "max": 2.50},
    "High Risk":        {"min": 2.50, "max": 4.00},
    "Medium-Long Term": {"min": 3.75, "max": 6.00},
    "Declined":         {"min": 0,    "max": 0},
}

# Financial ratio scoring
# Each ratio: Low Risk = 5, Standard = 10, High Risk = 15
# Special: Negative TNW adds 75 directly -- auto decline
FINANCIAL_RATIO_SCORES = {
    "current_ratio":   {"low": "> 2.0",      "std": "1.0-2.0",    "high": "< 1.0"},
    "tol_tnw":         {"low": "< 1.5",      "std": "1.5-3.0",    "high": "> 3.0"},
    "bad_debt_pct":    {"low": "< 1%",       "std": "1%-3%",      "high": "> 3%"},
    "tnw_pct_assets":  {"low": "> 30%",      "std": "10%-30%",    "high": "< 10%", "negative": 75},
    "debtor_days":     {"low": "< 45 days",  "std": "45-90 days", "high": "> 90 days"},
    "creditor_days":   {"low": "< 45 days",  "std": "45-90 days", "high": "> 90 days"},
    "capital_adequacy":{"low": "> 30% TOL",  "std": "15-30% TOL", "high": "< 15% TOL"},
}

# Final score weights
WEIGHTS = {
    "business_profile": 0.30,
    "financials":       0.40,
    "buyer_portfolio":  0.30,
}

# Buyer risk weights
BUYER_WEIGHTS = {
    "country_risk":  0.40,
    "industry_risk": 0.40,
    "customer_risk": 0.20,
}


# ============================================================
# SECTION 2 -- HELPER FUNCTIONS
# ============================================================

def get_payment_terms_score(days: int) -> tuple:
    """Returns risk score and payment term classification."""
    if days <= 360:
        for (min_d, max_d), score in PAYMENT_TERMS_RISK.items():
            if min_d <= days <= max_d:
                return score, "Short Term"
        return 20, "Short Term"
    elif days < 1460:
        return 20, "Medium-Long Term"
    else:
        return 40, "Long Term"


def get_country_risk_score(countries: list) -> tuple:
    """Returns highest country risk score and rating from buyer countries."""
    scores = []
    for country in countries:
        key    = country.lower().strip()
        rating = COUNTRY_RISK.get(key, COUNTRY_RISK["other"])
        score  = RATING_TO_SCORE.get(rating, 9)
        scores.append((score, rating, country))
    if not scores:
        return 9, "B2", "Unknown"
    scores.sort(reverse=True)
    return scores[0]


def get_concentration_score(top_buyer_pct: float) -> int:
    """Returns risk score based on buyer concentration."""
    if top_buyer_pct >= 75:   return 25
    elif top_buyer_pct >= 50: return 15
    elif top_buyer_pct >= 30: return 10
    else:                     return 0


def get_loss_ratio_score(loss_ratio: float) -> int:
    """Returns risk score based on historical bad debt loss ratio."""
    if loss_ratio >= 0.05:   return 25
    elif loss_ratio >= 0.03: return 15
    elif loss_ratio >= 0.01: return 10
    else:                    return 0


def get_premium_rate(tier: str, risk_score: int, term_classification: str = "Short Term") -> float:
    """Calculates premium rate based on tier, score and term classification."""
    if tier == "Declined":
        return 0.0
    if term_classification == "Medium-Long Term":
        r        = PREMIUM_RANGE["Medium-Long Term"]
        position = risk_score / 100
        return round(r["min"] + (position * (r["max"] - r["min"])), 2)
    r            = PREMIUM_RANGE.get(tier, PREMIUM_RANGE["High Risk"])
    tier_ranges  = {"Standard": (0, 29), "Enhanced": (30, 49), "High Risk": (50, 74)}
    t_min, t_max = tier_ranges.get(tier, (0, 100))
    position     = (risk_score - t_min) / max(t_max - t_min, 1)
    return round(r["min"] + (position * (r["max"] - r["min"])), 2)


# ============================================================
# SECTION 3 -- STREAM 1: BUSINESS PROFILE SCORING
# ============================================================

def score_business_profile(profile: dict) -> dict:
    """
    Stream 1 -- Scores the policyholder business profile.
    Returns raw score (0-100) and breakdown.
    """
    score             = 0
    breakdown         = {}
    industry_warnings = []

    # Industry risk
    industries = profile.get("industries", ["other"])
    if isinstance(industries, str):
        industries = [industries]

    ind_scores = []
    for ind in industries:
        ind_key  = ind.lower().strip()
        ind_data = INDUSTRY_RISK.get(ind_key, INDUSTRY_RISK["other"])
        ind_scores.append(ind_data["score"])
        if ind_data["score"] >= ind_data["off_cover_limit"]:
            industry_warnings.append(
                f"{ind.title()} score ({ind_data['score']}) exceeds off-cover limit ({ind_data['off_cover_limit']})"
            )

    industry_score = max(ind_scores)
    score         += industry_score
    breakdown["industry_risk"] = industry_score

    # Trade type risk
    trade_score = TRADE_TYPE_RISK.get(profile.get("trade_type", "domestic").lower(), 4)
    score      += trade_score
    breakdown["trade_type_risk"] = trade_score

    # Country risk
    country_score, worst_rating, worst_country = get_country_risk_score(
        profile.get("buyer_countries", ["other"])
    )
    score += country_score
    breakdown["country_risk"]  = country_score
    breakdown["worst_country"] = f"{worst_country} ({worst_rating} -> {country_score})"

    # Payment terms
    payment_score, term_class = get_payment_terms_score(
        profile.get("payment_terms_days", 30)
    )
    score += payment_score
    breakdown["payment_terms_risk"]          = payment_score
    breakdown["payment_term_classification"] = term_class

    # Buyer concentration
    conc_score = get_concentration_score(profile.get("top_buyer_percentage", 0))
    score     += conc_score
    breakdown["concentration_risk"] = conc_score

    # Loss ratio
    loss_score = get_loss_ratio_score(profile.get("loss_ratio", 0))
    score     += loss_score
    breakdown["loss_ratio_risk"] = loss_score

    # Business maturity
    years = profile.get("years_in_business", 5)
    if years < 2:   years_score = 15
    elif years < 5: years_score = 5
    else:           years_score = 0
    score += years_score
    breakdown["business_maturity_risk"] = years_score

    return {
        "raw_score":           min(score, 100),
        "breakdown":           breakdown,
        "industry_warnings":   industry_warnings,
        "term_classification": term_class,
        "worst_country":       worst_country,
        "worst_rating":        worst_rating,
    }


# ============================================================
# SECTION 4 -- STREAM 2: FINANCIAL RATIO SCORING
# ============================================================

def score_financial_ratios(financials: dict) -> dict:
    """
    Stream 2 -- Scores financial ratios extracted from uploaded
    financial statements by Nova Multimodal.
    Returns raw score (0-100) and breakdown.
    """
    score               = 0
    breakdown           = {}
    auto_decline        = False
    auto_decline_reason = None

    rev   = financials.get("annual_revenue", 1)
    cos   = financials.get("cost_of_sales", rev * 0.6)
    ca    = financials.get("current_assets", 0)
    cl    = financials.get("current_liabilities", 1)
    tol   = financials.get("total_liabilities", 0)
    tnw   = financials.get("tangible_net_worth", 0)
    ta    = financials.get("total_assets", 1)
    cap   = financials.get("capital", 0)
    bd_val    = financials.get("bad_debts", 0)
    debtors  = financials.get("debtors", 0)
    creditors = financials.get("creditors", 0)

    # Current Ratio
    cr = ca / cl if cl > 0 else 0
    if cr > 2.0:    cr_s, cr_c = 5,  "Low Risk"
    elif cr >= 1.0: cr_s, cr_c = 10, "Standard"
    else:           cr_s, cr_c = 15, "High Risk"
    score += cr_s
    breakdown["current_ratio"] = {"value": round(cr, 2), "category": cr_c, "score": cr_s}

    # TOL/TNW
    tt = tol / tnw if tnw > 0 else 999
    if tt < 1.5:    tt_s, tt_c = 5,  "Low Risk"
    elif tt <= 3.0: tt_s, tt_c = 10, "Standard"
    else:           tt_s, tt_c = 15, "High Risk"
    score += tt_s
    breakdown["tol_tnw"] = {"value": round(tt, 2) if tt != 999 else "N/A", "category": tt_c, "score": tt_s}

    # Bad Debt %
    bd_pct = (bd_val / rev * 100) if rev > 0 else 0
    if bd_pct < 1.0:    bd_s, bd_c = 5,  "Low Risk"
    elif bd_pct <= 3.0: bd_s, bd_c = 10, "Standard"
    else:               bd_s, bd_c = 15, "High Risk"
    score += bd_s
    breakdown["bad_debt_pct"] = {"value": f"{round(bd_pct, 2)}%", "category": bd_c, "score": bd_s}

    # TNW % of Total Assets
    if tnw < 0:
        auto_decline        = True
        auto_decline_reason = "Negative Tangible Net Worth -- company is technically insolvent"
        score += 75
        breakdown["tnw_pct_assets"] = {
            "value":    f"{tnw:,.2f}",
            "category": "NEGATIVE - Auto Decline",
            "score":    75
        }
    else:
        tnw_pct = (tnw / ta * 100) if ta > 0 else 0
        if tnw_pct > 30:    tnw_s, tnw_c = 5,  "Low Risk"
        elif tnw_pct >= 10: tnw_s, tnw_c = 10, "Standard"
        else:               tnw_s, tnw_c = 15, "High Risk"
        score += tnw_s
        breakdown["tnw_pct_assets"] = {
            "value":    f"{round(tnw_pct, 2)}%",
            "category": tnw_c,
            "score":    tnw_s
        }

    # Debtor Days
    dd = (debtors / rev * 365) if rev > 0 else 0
    if dd < 45:    dd_s, dd_c = 5,  "Low Risk"
    elif dd <= 90: dd_s, dd_c = 10, "Standard"
    else:          dd_s, dd_c = 15, "High Risk"
    score += dd_s
    breakdown["debtor_days"] = {"value": f"{round(dd, 1)} days", "category": dd_c, "score": dd_s}

    # Creditor Days
    cd = (creditors / cos * 365) if cos > 0 else 0
    if cd < 45:    cd_s, cd_c = 5,  "Low Risk"
    elif cd <= 90: cd_s, cd_c = 10, "Standard"
    else:          cd_s, cd_c = 15, "High Risk"
    score += cd_s
    breakdown["creditor_days"] = {"value": f"{round(cd, 1)} days", "category": cd_c, "score": cd_s}

    # Capital Adequacy
    ca_pct = (cap / tol * 100) if tol > 0 else 100
    if ca_pct > 30:    ca_s, ca_c = 5,  "Low Risk"
    elif ca_pct >= 15: ca_s, ca_c = 10, "Standard"
    else:              ca_s, ca_c = 15, "High Risk"
    score += ca_s
    breakdown["capital_adequacy"] = {"value": f"{round(ca_pct, 2)}%", "category": ca_c, "score": ca_s}

    return {
        "raw_score":           min(score, 100),
        "breakdown":           breakdown,
        "auto_decline":        auto_decline,
        "auto_decline_reason": auto_decline_reason,
    }


# ============================================================
# SECTION 5 -- STREAM 3: BUYER PORTFOLIO SCORING
# ============================================================

def score_single_buyer(buyer: dict, customer_risk_score: int) -> dict:
    """
    Scores a single buyer using:
      Country risk   (40%)
      Industry risk  (40%)
      Customer score (20%)

    Args:
        buyer: dict with keys -- name, country, industry, exposure_amount
        customer_risk_score: business profile raw score

    Returns:
        dict with buyer risk score and breakdown
    """
    country  = buyer.get("country", "other").lower().strip()
    rating   = COUNTRY_RISK.get(country, COUNTRY_RISK["other"])
    country_s   = RATING_TO_SCORE.get(rating, 9)

    industry = buyer.get("industry", "other").lower().strip()
    ind_s    = INDUSTRY_RISK.get(industry, INDUSTRY_RISK["other"])["score"]

    buyer_score = (
        (country_s           * BUYER_WEIGHTS["country_risk"])  +
        (ind_s               * BUYER_WEIGHTS["industry_risk"]) +
        (customer_risk_score * BUYER_WEIGHTS["customer_risk"])
    )

    return {
        "buyer_name":  buyer.get("name"),
        "country":     buyer.get("country"),
        "industry":    industry,
        "risk_score":  round(buyer_score, 2),
        "exposure":    buyer.get("exposure_amount", 0),
        "breakdown": {
            "country_risk":  f"{country} ({rating}) -> {country_s} x 40% = {round(country_s * 0.40, 2)}",
            "industry_risk": f"{industry} -> {ind_s} x 40% = {round(ind_s * 0.40, 2)}",
            "customer_risk": f"customer score {customer_risk_score} x 20% = {round(customer_risk_score * 0.20, 2)}",
        }
    }


def score_buyer_portfolio(buyers: list, customer_risk_score: int) -> dict:
    """
    Scores all buyers and combines into weighted average
    floored to nearest whole number using math.floor().

    Args:
        buyers: list of buyer dicts with exposure_amount
        customer_risk_score: business profile raw score

    Returns:
        dict with portfolio score and individual scores
    """
    if not buyers:
        return {"portfolio_score": 0, "buyer_scores": [], "total_exposure": 0}

    total_exposure = sum(b.get("exposure_amount", 0) for b in buyers)
    buyer_scores   = [score_single_buyer(b, customer_risk_score) for b in buyers]

    if total_exposure > 0:
        weighted_sum    = sum(b["risk_score"] * b["exposure"] for b in buyer_scores)
        portfolio_score = math.floor(weighted_sum / total_exposure)
    else:
        portfolio_score = math.floor(sum(b["risk_score"] for b in buyer_scores) / len(buyer_scores))

    return {
        "portfolio_score": portfolio_score,
        "buyer_scores":    buyer_scores,
        "total_exposure":  total_exposure,
    }


# ============================================================
# SECTION 6 -- MAIN SCORING FUNCTION
# ============================================================

def calculate_risk_score(profile: dict) -> dict:
    """
    Calculates final weighted trade credit insurance risk score.

    Final Score = (Business Profile x 0.30)
                + (Financial Ratios  x 0.40)
                + (Buyer Portfolio   x 0.30)

    Args:
        profile: dict with keys:
            business_name          (str)
            industries             (list)
            trade_type             (str)  -- export / domestic / both
            annual_turnover        (float)
            credit_sales_percentage(float)
            buyer_countries        (list)
            top_buyer_percentage   (float)
            payment_terms_days     (int)
            loss_ratio             (float)
            years_in_business      (int)
            buyers                 (list) -- name, country, industry, exposure_amount
            financials             (dict) -- extracted by Nova Multimodal

    Returns:
        dict with final score, tier, premium, and full breakdown
    """

    # Stream 1 -- Business Profile
    bp       = score_business_profile(profile)
    bp_score = bp["raw_score"]

    # Stream 2 -- Financial Ratios
    financials = profile.get("financials")
    if financials:
        fin                 = score_financial_ratios(financials)
        fin_score           = fin["raw_score"]
        auto_decline        = fin["auto_decline"]
        auto_decline_reason = fin["auto_decline_reason"]
    else:
        fin                 = {"raw_score": 50, "breakdown": {}, "auto_decline": False, "auto_decline_reason": None}
        fin_score           = 50
        auto_decline        = False
        auto_decline_reason = None

    # Stream 3 -- Buyer Portfolio
    buyer_result  = score_buyer_portfolio(profile.get("buyers", []), bp_score)
    buyer_score   = buyer_result["portfolio_score"]

    # Weighted Final Score
    weighted_score = (
        (bp_score    * WEIGHTS["business_profile"]) +
        (fin_score   * WEIGHTS["financials"])       +
        (buyer_score * WEIGHTS["buyer_portfolio"])
    )
    final_score    = math.floor(min(weighted_score, 100))
    term_class     = bp.get("term_classification", "Short Term")

    # Risk Tier
    if auto_decline:
        tier             = "Declined"
        tier_description = f"Auto decline -- {auto_decline_reason}"
    elif final_score >= 75:
        tier             = "Declined"
        tier_description = "Total risk score exceeds maximum threshold"
    elif bp["industry_warnings"]:
        tier             = "Declined"
        tier_description = f"Industry off-cover limit breached -- {'; '.join(bp['industry_warnings'])}"
    elif final_score < 30:
        tier             = "Standard"
        tier_description = "Low risk -- eligible for full coverage at standard rates"
    elif final_score < 50:
        tier             = "Enhanced"
        tier_description = "Moderate risk -- eligible for coverage with standard conditions"
    else:
        tier             = "High Risk"
        tier_description = "Elevated risk -- coverage available with restricted terms"

    # Premium Calculation
    premium_rate   = get_premium_rate(tier, final_score, term_class)
    credit_sales   = profile.get("annual_turnover", 0) * (profile.get("credit_sales_percentage", 100) / 100)
    annual_premium = round(credit_sales * (premium_rate / 100), 2)

    return {
        "business_name":       profile.get("business_name", "Unknown"),
        "final_score":         final_score,
        "risk_tier":           tier,
        "tier_description":    tier_description,
        "premium_rate":        f"{premium_rate}% of credit sales",
        "annual_premium":      f"{annual_premium:,.2f}",
        "credit_sales_volume": f"{credit_sales:,.2f}",
        "score_breakdown": {
            "business_profile": {
                "raw_score":      bp_score,
                "weighted_score": round(bp_score * WEIGHTS["business_profile"], 2),
                "detail":         bp["breakdown"],
            },
            "financial_ratios": {
                "raw_score":      fin_score,
                "weighted_score": round(fin_score * WEIGHTS["financials"], 2),
                "detail":         fin["breakdown"],
            },
            "buyer_portfolio": {
                "raw_score":      buyer_score,
                "weighted_score": round(buyer_score * WEIGHTS["buyer_portfolio"], 2),
                "buyers":         buyer_result["buyer_scores"],
            },
        },
        "industry_warnings": bp["industry_warnings"],
    }


# ============================================================
# SECTION 7 -- TEST
# ============================================================

if __name__ == "__main__":

    import time

    # Test 1 -- Healthy UK manufacturer with financials and buyers
    profile_1 = {
        "business_name":            "SoundFinance Ltd",
        "industries":               ["manufacturing"],
        "trade_type":               "both",
        "annual_turnover":          4000000,
        "credit_sales_percentage":  75,
        "buyer_countries":          ["United Kingdom", "Germany"],
        "top_buyer_percentage":     25,
        "payment_terms_days":       45,
        "loss_ratio":               0.01,
        "years_in_business":        7,
        "buyers": [
            {"name": "BuyerA UK",      "country": "United Kingdom", "industry": "retail",        "exposure_amount": 200000},
            {"name": "BuyerB Germany", "country": "Germany",        "industry": "manufacturing", "exposure_amount": 150000},
        ],
        "financials": {
            "annual_revenue":       4000000,
            "current_assets":       800000,
            "current_liabilities":  350000,
            "total_liabilities":    1200000,
            "tangible_net_worth":   600000,
            "total_assets":         1800000,
            "capital":              400000,
            "bad_debts":            32000,
            "debtors":              450000,
            "creditors":            280000,
            "cost_of_sales":        2400000,
        }
    }

    # Test 2 -- High risk exporter with negative TNW
    profile_2 = {
        "business_name":            "HighRisk Traders Ltd",
        "industries":               ["construction"],
        "trade_type":               "export",
        "annual_turnover":          2000000,
        "credit_sales_percentage":  90,
        "buyer_countries":          ["Venezuela", "Lebanon"],
        "top_buyer_percentage":     80,
        "payment_terms_days":       120,
        "loss_ratio":               0.06,
        "years_in_business":        1,
        "buyers": [
            {"name": "Buyer Venezuela", "country": "Venezuela", "industry": "construction", "exposure_amount": 300000},
            {"name": "Buyer Lebanon",   "country": "Lebanon",   "industry": "retail",       "exposure_amount": 200000},
        ],
        "financials": {
            "annual_revenue":       2000000,
            "current_assets":       200000,
            "current_liabilities":  500000,
            "total_liabilities":    1500000,
            "tangible_net_worth":   -200000,
            "total_assets":         1300000,
            "capital":              50000,
            "bad_debts":            80000,
            "debtors":              300000,
            "creditors":            450000,
            "cost_of_sales":        1600000,
        }
    }

    for test_profile in [profile_1, profile_2]:
        result = calculate_risk_score(test_profile)
        logging.info("=" * 60)
        logging.info(f"Business        : {result['business_name']}")
        logging.info(f"Final Score     : {result['final_score']} / 100")
        logging.info(f"Risk Tier       : {result['risk_tier']}")
        logging.info(f"Description     : {result['tier_description']}")
        logging.info(f"Premium Rate    : {result['premium_rate']}")
        logging.info(f"Annual Premium  : {result['annual_premium']}")
        bd_result = result["score_breakdown"]
        logging.info(f"Business Profile : raw={bd_result['business_profile']['raw_score']}  weighted={bd_result['business_profile']['weighted_score']}")
        logging.info(f"Financial Ratios : raw={bd_result['financial_ratios']['raw_score']}  weighted={bd_result['financial_ratios']['weighted_score']}")
        logging.info(f"Buyer Portfolio  : raw={bd_result['buyer_portfolio']['raw_score']}  weighted={bd_result['buyer_portfolio']['weighted_score']}")
        for buyer_item in bd_result["buyer_portfolio"]["buyers"]:
            logging.info(f"  {buyer_item['buyer_name']:<25}  Score: {buyer_item['risk_score']}")
        if result["industry_warnings"]:
            for warning in result["industry_warnings"]:
                logging.warning(f"WARNING: {warning}")

    # Measure underwriting engine speed (average of 1000 runs)
    runs    = 1000
    start   = time.time()
    for _ in range(runs):
        calculate_risk_score(profile_1)
    elapsed = (time.time() - start) / runs * 1000
    logging.info(f"Underwriting time (avg over {runs} runs): {elapsed:.3f} ms")