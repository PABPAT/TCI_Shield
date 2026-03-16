import streamlit as st
import boto3
from config import AWS_REGION

st.title("Dashboard")
st.write("All policies issued by TCI Shield.")

def get_all_policies():
    try:
        dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
        table = dynamodb.Table("tci_customers")
        response = table.scan()
        items = response.get("Items", [])
        if not items:
            return []
        all_policies = []
        for customer in items:
            for policy in customer.get("policies", []):
                all_policies.append({
                    "business_name":     customer.get("business_name", "-"),
                    "country":           customer.get("country", "-"),
                    "industry":          customer.get("industry", "-"),
                    "policy_id":         policy.get("policy_id", "-"),
                    "status":            policy.get("status", "-"),
                    "risk_tier":         policy.get("risk_tier", "-"),
                    "risk_score":        policy.get("risk_score", "-"),
                    "premium_rate":      policy.get("premium_rate", "-"),
                    "annual_premium":    policy.get("annual_premium", "-"),
                    "policy_start_date": policy.get("policy_start_date", "-"),
                    "policy_end_date":   policy.get("policy_end_date", "-"),
                })
        return sorted(all_policies, key=lambda x: x["policy_start_date"], reverse=True)
    except Exception as e:
        st.error(f"Error fetching policies: {e}")
        return []

if st.button("Refresh"):
    st.rerun()

policies = get_all_policies()

if not policies:
    st.info("No policies found. Complete an application first.")
else:
    # Summary metrics
    total     = len(policies)
    active    = len([p for p in policies if p["status"] == "ACTIVE"])
    declined  = len([p for p in policies if p["risk_tier"] == "Declined"])

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Policies", total)
    col2.metric("Active Policies", active)
    col3.metric("Declined", declined)

    st.subheader("All Policies")
    import pandas as pd
    df = pd.DataFrame(policies)
    df.columns = [
        "Business", "Country", "Industry",
        "Policy ID", "Status", "Risk Tier", "Risk Score",
        "Premium Rate", "Annual Premium",
        "Start Date", "End Date"
    ]
    st.dataframe(df, use_container_width=True)