# ISSUES LOG -- Trade Credit Insurance Agent
# Purpose: Document every bug, fix and lesson learned during development
# Format: Issue -> Root Cause -> Fix -> Lesson

---

## ISSUE 001 -- AWS Bedrock Operation Not Allowed
Date      : 21 Feb 2026
File      : test_nova.py
Status    : Resolved

### Symptom
    botocore.errorfactory.ValidationException: Operation not allowed

### Root Cause
    The original AWS account had Bedrock blocked at account level.
    Even root credentials and AdministratorAccess could not invoke models.

### Fix
    Created a new AWS account. Bedrock worked immediately.

### Lesson
    - Always test Bedrock access on a new account before building
    - "Operation not allowed" in Bedrock = account-level block, not IAM
    - Root credentials not working = account-level issue, not permissions

---

## ISSUE 002 -- Wrong Model ID
Date      : 21 Feb 2026
File      : test_nova.py
Status    : Resolved

### Symptom
    ValidationException: The provided model identifier is invalid

### Root Cause
    Used "us.amazon.nova-lite-v1:0" but account required
    "amazon.nova-lite-v1:0" without the "us." cross-region prefix.

### Fix
    Listed available models:
        aws bedrock list-foundation-models --region us-east-1
    Updated modelId to "amazon.nova-lite-v1:0"

### Lesson
    - Never hardcode model IDs -- always verify against your account
    - Use list_foundation_models() to get exact IDs available

---

## ISSUE 003 -- Wrong Bedrock Method Name
Date      : 21 Feb 2026
File      : test_nova.py
Status    : Resolved

### Symptom
    AttributeError: BedrockRuntime object has no attribute 'invoke_endpoint'

### Root Cause
    Used invoke_endpoint (SageMaker method) instead of invoke_model (Bedrock method).

### Fix
    Changed client.invoke_endpoint() to client.invoke_model()

### Lesson
    - Bedrock uses invoke_model, not invoke_endpoint
    - invoke_endpoint belongs to SageMaker -- different service entirely

---

## ISSUE 004 -- Malformed Request Body
Date      : 21 Feb 2026
File      : test_nova.py
Status    : Resolved

### Symptom
    ValidationException: Malformed input request: required key [messages] not found

### Root Cause
    Request body was missing the messages key at the top level.

### Fix
    Restructured body to place messages at the top level:
        body=json.dumps({
            "messages": [{"role": "user", "content": [{"text": message}]}],
            "inferenceConfig": {"maxTokens": 500}
        })

### Lesson
    - Nova Lite expects messages at the top level of the request body
    - Always match the exact schema from AWS documentation

---

## ISSUE 005 -- ModuleNotFoundError: database
Date      : 21 Feb 2026
File      : tci_agent.py
Status    : Resolved

### Symptom
    ModuleNotFoundError: No module named 'database'

### Root Cause
    database.py and config.py had not been created yet.
    Only underwriting_engine.py existed in the project.

### Fix
    Created config.py, database.py in the same folder as tci_agent.py.

### Lesson
    - All imported modules must exist as .py files in the same directory
    - Import errors = file missing or wrong path, nothing else

---

## ISSUE 006 -- Strands Agent Double Printing
Date      : 21 Feb 2026
File      : tci_agent.py
Status    : Resolved

### Symptom
    Agent response printed twice in console.

### Root Cause
    Strands has a default callback_handler that streams output to console.
    Our manual print() statement added a second copy.

### Fix
    Removed manual print() statements. Let Strands handle all output.

### Lesson
    - Strands Agent prints responses internally by default
    - Do not add manual print() for agent responses

---

## ISSUE 007 -- Stale Session State Between Conversations
Date      : 21 Feb 2026
File      : tci_agent.py
Status    : Resolved

### Symptom
    INFO - ToolResult has already been updated, skipping overwrite
    Agent enters inconsistent state mid-conversation.

### Root Cause
    Global orchestrator retained conversation history between runs.
    Global session dict retained data from previous conversations.

### Fix
    Added reset_session() to clear all session fields.
    Moved Agent creation inside run_conversation() for fresh state each time.

### Lesson
    - Global state is dangerous in conversational agents
    - Always reset session AND recreate agent for each new conversation
    - Never reuse an Agent instance across separate conversations

---

## ISSUE 008 -- Pydantic Models Unresolved Reference
Date      : 21 Feb 2026
File      : tci_agent.py
Status    : Resolved

### Symptom
    Unresolved reference 'models', 'BusinessInfo', 'BuyerInfo', 'FinancialData'

### Root Cause
    models.py file was not created in the project folder.

### Fix
    Created models.py in the same folder as tci_agent.py.

### Lesson
    - All project modules must be in the same directory
    - PyCharm shows unresolved reference before runtime -- fix early

---

## ISSUE 009 -- Incomplete Validation Allowing Agent to Skip Steps
Date      : 21 Feb 2026
File      : tci_agent.py
Status    : Resolved

### Symptom
    Agent skipping data collection steps and proceeding with incomplete data.

### Root Cause
    Guards added one at a time. No comprehensive validation.

### Fix
    Added 4 validation functions:
        validate_business_info()  -- 6 business fields
        validate_buyer_info()     -- buyer fields + per-buyer validation
        validate_financial_data() -- 11 financial figures, rejects zeros
        validate_all()            -- runs all 3 in sequence

### Lesson
    - Build comprehensive validators early, not incrementally
    - validate_all() single entry point is cleaner than multiple guards
    - Descriptive error messages tell Nova exactly what to collect next

---

## ISSUE 010 -- Cannot Find Reference 'credentials_resolvers' in smithy_aws_core
Date      : 12 Mar 2026
File      : voice_agent.py
Status    : Resolved

### Symptom
    PyCharm warning: Cannot find reference 'credentials_resolvers' in 'smithy_aws_core'
    Then at runtime:
    ModuleNotFoundError: No module named 'smithy_aws_core.credentials_resolvers'

### Root Cause
    smithy_aws_core version 0.4.0 reorganized its internal modules.
    The credentials_resolvers submodule was renamed to identity.
    The import from the official AWS docs was written for an older version.

### Fix
    Old import (broken):
        from smithy_aws_core.credentials_resolvers.environment import EnvironmentCredentialsResolver

    New import (correct for v0.4.0):
        from smithy_aws_core.identity.environment import EnvironmentCredentialsResolver

    Found by running:
        python -c "import pkgutil; import smithy_aws_core;
        [print(m.name) for m in pkgutil.walk_packages(
        smithy_aws_core.__path__, smithy_aws_core.__name__ + '.')]"

### Lesson
    - AWS experimental SDKs change module structure between versions
    - Official docs may be outdated -- always verify against installed version
    - Use pkgutil.walk_packages() to discover actual module structure
    - PyCharm warning + ModuleNotFoundError = module path has changed

---

## ISSUE 011 -- SigV4AuthScheme Missing Required 'service' Argument
Date      : 12 Mar 2026
File      : voice_agent.py
Status    : Resolved

### Symptom
    TypeError: SigV4AuthScheme.__init__() missing 1 required keyword-only argument: 'service'

### Root Cause
    Newer version of smithy_aws_core requires the service name to be
    explicitly passed to SigV4AuthScheme. Older examples omitted it.

### Fix
    Old:  SigV4AuthScheme()
    New:  SigV4AuthScheme(service="bedrock")

### Lesson
    - Always check __init__ signatures when upgrading SDK packages
    - Required arguments added in newer versions break old code silently

---

## ISSUE 012 -- Config Parameter Name Changes in aws_sdk_bedrock_runtime
Date      : 12 Mar 2026
File      : voice_agent.py
Status    : Resolved

### Symptom
    TypeError: Config.__init__() got an unexpected keyword argument 'http_auth_scheme_resolver'
    TypeError: Config.__init__() got an unexpected keyword argument 'http_auth_schemes'

### Root Cause
    Parameter names in Config changed between SDK versions:
        http_auth_scheme_resolver -> auth_scheme_resolver
        http_auth_schemes         -> auth_schemes

### Fix
    Used this command to inspect actual parameter names:
        python -c "from aws_sdk_bedrock_runtime.config import Config; help(Config.__init__)"

    Updated Config call:
        config = Config(
            endpoint_uri=f"https://bedrock-runtime.{region}.amazonaws.com",
            region=region,
            aws_credentials_identity_resolver=EnvironmentCredentialsResolver(),
            auth_scheme_resolver=HTTPAuthSchemeResolver(),
            auth_schemes={"aws.auth#sigv4": SigV4AuthScheme(service="bedrock")}
        )

### Lesson
    - When SDK upgrades break parameter names, use help() to see actual names
    - Never guess parameter names -- inspect the class directly
    - http_ prefix was dropped from auth-related Config parameters in v0.4.0
    - help(ClassName.__init__) is the fastest way to see all valid parameters

---

## ISSUE 013 -- collect_buyer_info Validation Loop
Date      : 16 Mar 2026
File      : tci_agent.py
Status    : Resolved

### Symptom
    Agent kept asking for buyer count repeatedly in an infinite loop.
    collect_buyer_info was failing Pydantic validation every time.
    Customer provided buyer details multiple times with no progress.

### Root Cause
    set_buyer_count tool was not being called before collect_buyer_info.
    session["declared_buyer_count"] was None.
    BuyerInfo Pydantic model requires declared_buyer_count to match
    the number of buyers provided -- with None it always failed.

### Fix
    Added fallback at the top of collect_buyer_info:
        if not session.get("declared_buyer_count"):
            session["declared_buyer_count"] = len(buyers)
    This sets the count from the buyers list if set_buyer_count
    was never called by the agent.

### Lesson
    - Always add fallbacks when session state may be None
    - Pydantic validation errors should be logged immediately
    - Infinite loops in agents are almost always a tool returning
      an error that the agent cannot resolve
    - Never rely on a separate tool being called before validation
      runs -- add defensive fallbacks inside the tool itself

## OPEN ISSUES
# Issues identified but not yet resolved

None currently.

---

## HOW TO USE THIS FILE
- Add new issues as they occur during development
- Never delete resolved issues -- they are your learning record
- Review before starting each session to remember context
- Share with future team members as onboarding documentation