import streamlit as st
import pandas as pd
import altair as alt

from mvvm.services.api_client import ApiClient
from mvvm.viewmodels.rbac_vm import RBACViewModel

st.title("🛡️ RBAC Access Metrics")
st.write("Real-time telemetry of Casbin Role-Based Access Control decisions.")

if "token" not in st.session_state or not st.session_state.token:
    st.error("Please log in to access this page.")
    st.stop()

# Build the ViewModel using the token from session state
api_url = st.secrets.get("API_URL", "http://127.0.0.1:8000")
client = ApiClient(api_url, st.session_state.token)
vm = RBACViewModel(client)

try:
    with st.spinner("Loading metrics..."):
        metrics = vm.get_rbac_metrics()
except Exception as e:
    st.error(f"Failed to load metrics: {e}")
    st.stop()

# ---------------------------------------------------------
# Top-level KPIs
# ---------------------------------------------------------
st.markdown("### Top-Level Enforcement KPIs")
col1, col2, col3 = st.columns(3)

total_allowed = metrics.get("total_allowed", 0)
total_denied = metrics.get("total_denied", 0)
total_requests = total_allowed + total_denied

if total_requests > 0:
    deny_rate = (total_denied / total_requests) * 100
else:
    deny_rate = 0.0

col1.metric("Total Enforcement Checks", total_requests)
col2.metric("Unauthorized Requests Blocked", total_denied, f"{deny_rate:.1f}% Deny Rate")
col3.metric("Successful Authorizations", total_allowed)

st.divider()

# ---------------------------------------------------------
# Charts Row
# ---------------------------------------------------------
col_chart1, col_chart2 = st.columns([1, 1])

# 1. Role Distribution Chart
with col_chart1:
    st.markdown("#### API Usage by Role")
    role_dist = metrics.get("role_distribution", {})
    if role_dist:
        # Convert dictionary to DataFrame for charting
        df_roles = pd.DataFrame(list(role_dist.items()), columns=["Role", "Total Requests"])
        
        # We can use Altair for a nice pie/donut chart
        base = alt.Chart(df_roles).encode(
            theta=alt.Theta("Total Requests:Q", stack=True),
            color=alt.Color("Role:N", scale=alt.Scale(scheme='tableau10')),
            tooltip=["Role", "Total Requests"]
        )
        pie = base.mark_arc(innerRadius=50)
        st.altair_chart(pie, use_container_width=True)
    else:
        st.info("No role distribution data available yet.")

# 2. Daily Trends
with col_chart2:
    st.markdown("#### Access Decisions Over Time")
    trend_data = metrics.get("trend_data", [])
    if trend_data:
        df_trends = pd.DataFrame(trend_data)
        # Create a stacked bar chart mapping Action (Allowed vs Denied) to colors
        bar_chart = alt.Chart(df_trends).mark_bar().encode(
            x=alt.X('date:T', title='Date', axis=alt.Axis(format='%Y-%m-%d')),
            y=alt.Y('count:Q', title='Requests'),
            color=alt.Color('action:N', scale=alt.Scale(domain=['ALLOWED', 'DENIED'], range=['#2e7d32', '#d32f2f'])),
            tooltip=['date', 'action', 'count']
        ).properties(height=300)
        st.altair_chart(bar_chart, use_container_width=True)
    else:
        st.info("No trend data available yet.")

st.divider()

# ---------------------------------------------------------
# Recent Denials Table
# ---------------------------------------------------------
st.markdown("#### Recent Access Denials (403 Forbidden)")
recent_denials = metrics.get("recent_denials", [])

if recent_denials:
    df_denials = pd.DataFrame(recent_denials)
    # Rename columns for display
    df_denials = df_denials.rename(columns={
        "timestamp": "Time",
        "username": "User",
        "role": "Role",
        "endpoint": "Endpoint Accessed",
        "method": "HTTP Method"
    })
    
    # Clean up timestamps
    df_denials["Time"] = pd.to_datetime(df_denials["Time"]).dt.strftime("%Y-%m-%d %H:%M:%S")

    # Apply minor styling (e.g., highlighting the method column)
    def color_method(val):
        color = 'red' if val in ['DELETE', 'PUT'] else 'orange' if val == 'POST' else 'blue'
        return f'color: {color}; font-weight: bold'

    styled_df = df_denials.style.map(color_method, subset=['HTTP Method'])
    st.dataframe(styled_df, use_container_width=True, hide_index=True)
else:
    st.success("No unauthorized access attempts recently! The perimeter is secure.")
