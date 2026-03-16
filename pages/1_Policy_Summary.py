import streamlit as st
import boto3
from config import AWS_REGION

st.title("Policy Summary")
st.write("View your latest issued policy.")

def get_latest_policy():
    try:
        dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
        table = dynamodb.Table("tci_customers")
        response = table.scan()
        items = response.get("Items", [])
        if not items:
            return None, None
        latest_customer = sorted(
            items,
            key=lambda x: x.get("created_at", ""),
            reverse=True
        )[0]
        policies = latest_customer.get("policies", [])
        if not policies:
            return latest_customer, None
        latest_policy = sorted(
            policies,
            key=lambda x: x.get("policy_start_date", ""),
            reverse=True
        )[0]
        return latest_customer, latest_policy
    except Exception as e:
        st.error(f"Error fetching policy: {e}")
        return None, None

if st.button("Refresh"):
    st.rerun()

customer, policy = get_latest_policy()

if not customer:
    st.info("No policies found. Complete an application first.")
else:
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Business Details")
        st.write(f"**Business:** {customer.get('business_name', '-')}")
        st.write(f"**Industry:** {customer.get('industry', '-')}")
        st.write(f"**Country:** {customer.get('country', '-')}")
        st.write(f"**Trade Type:** {customer.get('trade_type', '-')}")
        st.write(f"**Annual Turnover:** £{float(customer.get('annual_turnover', 0)):,.2f}")

    with col2:
        st.subheader("Policy Details")
        if policy:
            st.write(f"**Policy ID:** {policy.get('policy_id', '-')}")
            st.write(f"**Status:** {policy.get('status', '-')}")
            st.write(f"**Risk Tier:** {policy.get('risk_tier', '-')}")
            st.write(f"**Risk Score:** {policy.get('risk_score', '-')}")
            st.write(f"**Premium Rate:** {policy.get('premium_rate', '-')}%")
            st.write(f"**Annual Premium:** £{float(policy.get('annual_premium', 0)):,.2f}")
            st.write(f"**Start Date:** {policy.get('policy_start_date', '-')}")
            st.write(f"**End Date:** {policy.get('policy_end_date', '-')}")
        else:
            st.info("No policy issued yet.")

    if policy and policy.get("covered_buyers"):
        st.subheader("Covered Buyers")
        for buyer in policy.get("covered_buyers", []):
            st.write(f"- {buyer}")