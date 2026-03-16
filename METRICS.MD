# AI Trade Credit Insurance Agent -- Project Metrics Tracker
# Last Updated: 21 Feb 2026
# Status: Work in Progress -- figures to be replaced with real measurements on completion

---

## HOW TO USE THIS FILE
- Each section tracks metrics for one module
- [ESTIMATED] = placeholder, replace with real figure after testing
- [MEASURED] = confirmed real figure from actual testing
- Final resume bullet points at the bottom -- update as modules complete

---

## MODULE 1 -- UNDERWRITING ENGINE
# Status: Complete
# File: underwriting_engine.py

### Confirmed Figures (count from code)
- Countries assessed              : 238  [MEASURED -- count of COUNTRY_RISK keys]
- Risk factors (Stream 1)         : 7    [MEASURED -- industry, trade, country, payment, concentration, loss ratio, maturity]
- Financial ratios (Stream 2)     : 7    [MEASURED -- current ratio, TOL/TNW, bad debt%, TNW%, debtor days, creditor days, capital adequacy]
- Industry sectors                : 11   [MEASURED -- count of INDUSTRY_RISK keys]
- Risk tiers                      : 4    [MEASURED -- Standard, Enhanced, High Risk, Declined]
- Decline rules                   : 3    [MEASURED -- score>=75, negative TNW, industry off-cover breach]
- Premium range                   : 1% to 6% of credit sales  [MEASURED]
- Weighted streams                : 3    [MEASURED -- Business 30%, Financials 40%, Buyers 30%]

### Performance Figures (to be measured)
- Average underwriting time       : 0.013 ms (avg over 1000 runs)  [MEASURED -- 21 Feb 2026]
- Accuracy vs manual underwriting : [TO BE MEASURED] -- compare 10 sample cases with expert decision

### Business Baseline (industry standard)
- Traditional underwriting time   : 5-7 business days  [INDUSTRY STANDARD -- cite Euler Hermes]
- Manual financial analysis time  : 2-3 hours per application  [INDUSTRY STANDARD]
- Market size                     : $12B+ globally  [CITE -- ICISA Annual Report]

---

## MODULE 2 -- DATABASE
# Status: Complete
# File: database.py

### Confirmed Figures
- DynamoDB tables                 : 2    [MEASURED -- tci_customers, tci_buyers]
- Data entities tracked           : 4    [MEASURED -- customers, buyers, policies, claims]
- ID formats defined              : 4    [MEASURED -- CUST, POL, CLM, REG]

---

## MODULE 3 -- STRANDS AGENT
# Status: Complete
# File: tci_agent.py, models.py

### Confirmed Figures
- Number of agents                : 1 orchestrator  [MEASURED]
- Number of tools                 : 8  [MEASURED -- get_progress, set_buyer_count, collect_business_info, collect_buyer_info, collect_financial_data, run_underwriting, generate_policy_options, issue_policy]
- Conversation steps              : 20  [MEASURED]
- Pydantic models                 : 4  [MEASURED -- BusinessInfo, Buyer, BuyerInfo, FinancialData]
- Validation fields               : 30+ across all models  [MEASURED]
- Tool guards implemented         : all 8 tools have validation  [MEASURED]
- Progress tracking flags         : 5  [MEASURED -- business, buyers, financials, underwriting, policy]
- Issues resolved during testing  : 23 issues (Issues 008-031)  [MEASURED]

### Performance Figures
- Underwriting engine time        : 0.013ms  [MEASURED]
- Nova API round trip             : 2-5 seconds per call  [MEASURED]
- Full conversation end-to-end    : [TO BE MEASURED] -- time full test run
- Data collection reliability     : All fields collected correctly with Pydantic validation  [MEASURED]
- Conversation order flexibility  : Agent collects all data correctly regardless of order  [MEASURED]

---

## MODULE 4 -- NOVA SONIC VOICE
# Status: Not Started

### Target Figures
- Voice to policy time            : [ESTIMATED under 10 minutes] -- measure end to end
- Speech recognition accuracy     : [TO BE MEASURED] -- test with 10 sample conversations
- Languages supported             : [TARGET 1 -- English] -- expand post hackathon

---

## MODULE 5 -- NOVA MULTIMODAL DOCUMENT ANALYSIS
# Status: Complete
# File: document_extractor.py

### Confirmed Figures
- Financial ratios extracted      : 11   [MEASURED]
- Document types supported        : 5    [MEASURED -- PDF, DOCX, XLSX, CSV, TXT]
- Extraction accuracy             : 100% on test file (11/11 fields correct)  [MEASURED]
- Extraction time                 : 1.05 seconds  [MEASURED -- 21 Feb 2026]
- Pydantic validation             : Applied after extraction  [MEASURED]

### Performance
- Document size tested            : 483 bytes (TXT)  [MEASURED]
- Nova response size              : 331 characters  [MEASURED]
- Fields extracted correctly      : 11 of 11  [MEASURED]
- Validation passed               : Yes  [MEASURED]

---

## MODULE 6 -- POLICY COMPARISON UI
# Status: Not Started

### Target Figures
- Policy tiers displayed          : [TARGET 3 -- Standard, Enhanced, High Risk]
- Data points per policy          : [TO BE MEASURED] -- count fields shown in UI

---

## MODULE 7 -- PDF POLICY ISSUANCE
# Status: Not Started

### Target Figures
- Policy document sections        : [TO BE MEASURED] -- count sections in template
- Time to generate PDF            : [TO BE MEASURED] -- measure in testing

---

## FINAL COMBINED METRICS
# To be completed when all modules are done

### Core Performance
- End-to-end time (voice to PDF)  : [TO BE MEASURED]
- Traditional process time        : 5-7 business days  [INDUSTRY STANDARD]
- Time reduction                  : [CALCULATE -- ((traditional - new) / traditional) x 100]%

### Technical Depth
- Total risk factors              : [SUM all factors across all modules]
- Countries covered               : 238
- Financial ratios automated      : 7
- Nova models used                : [TARGET 3 -- Sonic, Lite, Multimodal]
- AWS services used               : [COUNT on completion]

### Business Impact
- Target market                   : 5.5M SMEs in UK  [CITE -- Companies House stats]
- Market size                     : $12B+ globally  [CITE -- ICISA]
- Cost of traditional broker      : 0.25-1.5% of turnover  [INDUSTRY STANDARD]

---

## RESUME BULLET POINTS
# Update versions as modules complete

### Current Version (Underwriting Engine complete -- 21 Feb 2026)
"Built a 3-stream weighted underwriting engine for trade credit insurance,
scoring 14 risk factors across 238 countries with automated financial ratio
analysis in 0.013ms average -- compared to 5-7 business day traditional process.
Foundation of an AI agent targeting a $12B+ global market."

### Target Version (All modules complete -- replace [X] with real figures)
"Built an end-to-end AI trade credit insurance platform reducing policy
issuance from 5-7 days to [X] minutes, using Amazon Nova Sonic for voice
intake, Nova Multimodal for automated financial analysis ([X] ratios extracted),
and a 3-stream underwriting engine covering 238 countries and [X] risk factors
-- deployed on AWS using Strands Agents, Lambda, DynamoDB and S3."

---

## HOW TO MEASURE KEY FIGURES

### Measure underwriting engine speed:
    import time
    start = time.time()
    result = calculate_risk_score(profile)
    elapsed = time.time() - start
    logging.info(f"Underwriting time: {elapsed:.3f} seconds")

### Measure end-to-end time:
    Record time from first voice input to PDF download link generated.
    Run 5 test cases and take average.

### Measure extraction accuracy:
    Take 10 real financial statements.
    Extract manually -- record figures.
    Run through Nova Multimodal -- record figures.
    Accuracy = (matching fields / total fields) x 100