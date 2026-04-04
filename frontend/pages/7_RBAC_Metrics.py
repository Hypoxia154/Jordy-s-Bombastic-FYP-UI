import streamlit as st
import pandas as pd
import altair as alt

from mvvm.services.api_client import ApiClient
from mvvm.viewmodels.rbac_vm import RBACViewModel

st.title("RBAC Access Metrics")
st.write("Real-time telemetry of Casbin Role-Based Access Control decisions.")

if "token" not in st.session_state or not st.session_state.token:
    st.error("Please log in to access this page.")
    st.stop()

# build the viewmodel using the token from session state
api_url = st.secrets.get("API_URL", "http://127.0.0.1:8000")
client = ApiClient(api_url, st.session_state.token)
vm = RBACViewModel(client)

try:
    with st.spinner("Loading metrics..."):
        metrics = vm.get_rbac_metrics()
except Exception as e:
    st.error(f"Failed to load metrics: {e}")
    st.stop()

# top-level kpis
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

# charts row
col_chart1, col_chart2 = st.columns([1, 1])

# role distribution chart
with col_chart1:
    with st.container(border=True):
        st.markdown("#### API Usage by Role")
        role_dist = metrics.get("role_distribution", {})
        if role_dist:
            # convert dictionary to dataframe for charting
            df_roles = pd.DataFrame(list(role_dist.items()), columns=["Role", "Total Requests"])
            
            # we can use altair for a nice pie/donut chart
            base = alt.Chart(df_roles).encode(
                theta=alt.Theta("Total Requests:Q", stack=True),
                color=alt.Color("Role:N", scale=alt.Scale(scheme='tableau10'), legend=alt.Legend(orient="bottom", title="Role")),
                tooltip=["Role", "Total Requests"]
            )
            pie = base.mark_arc(innerRadius=50).properties(height=300)
            st.altair_chart(pie, width="stretch")
        else:
            st.info("No role distribution data available yet.")

# daily trends
with col_chart2:
    with st.container(border=True):
        st.markdown("#### Access Decisions Over Time")
        trend_data = metrics.get("trend_data", [])
        if trend_data:
            df_trends = pd.DataFrame(trend_data)
            # create a stacked bar chart mapping action (allowed vs denied) to colors
            bar_chart = alt.Chart(df_trends).mark_bar().encode(
                x=alt.X('date:T', title='Date', axis=alt.Axis(format='%Y-%m-%d')),
                y=alt.Y('count:Q', title='Requests'),
                color=alt.Color('action:N', scale=alt.Scale(domain=['ALLOWED', 'DENIED'], range=['#2e7d32', '#d32f2f']), legend=alt.Legend(orient="bottom", title="Decision")),
                tooltip=[alt.Tooltip('date:T', title='Date', format='%Y-%m-%d'), alt.Tooltip('action:N', title='Action'), alt.Tooltip('count:Q', title='Requests')]
            ).properties(height=300)
            st.altair_chart(bar_chart, width="stretch")
        else:
            st.info("No trend data available yet.")

st.divider()

# recent denials table
st.markdown("#### Recent Access Denials (403 Forbidden)")
recent_denials = metrics.get("recent_denials", [])

if recent_denials:
    df_denials = pd.DataFrame(recent_denials)
    # rename columns for display
    df_denials = df_denials.rename(columns={
        "timestamp": "Time",
        "username": "User",
        "role": "Role",
        "endpoint": "Endpoint Accessed",
        "method": "HTTP Method"
    })
    
    # clean up timestamps
    df_denials["Time"] = pd.to_datetime(df_denials["Time"]).dt.strftime("%Y-%m-%d %H:%M:%S")

    # apply minor styling (e.g., highlighting the method column)
    def color_method(val):
        color = 'red' if val in ['DELETE', 'PUT'] else 'orange' if val == 'POST' else 'blue'
        return f'color: {color}; font-weight: bold'

    styled_df = df_denials.style.map(color_method, subset=['HTTP Method'])
    st.dataframe(styled_df, width="stretch", hide_index=True)
else:
    st.info(
        "**0 Denials is a feature, not a bug!** 🛡️\n\n"
        "Our frontend UI proactively hides unauthorized buttons and routes from users before they can even try to click them. "
        "This is called **Defense-in-Depth**. \n\n"
        "However, if a malicious actor bypassed the frontend and tried to hit the API directly using Postman or a script, "
        "Casbin would catch it. You can prove this using the simulator below."
    )

st.divider()

# Denies simulator
st.markdown("### Denial Simulator")
st.write(
    "Test the Casbin authorization engine live. Select a role and an endpoint to see if the "
    "backend intercepts the request. (Simulations will appear in the charts above after testing)."
)

# render flash message from a previous simulation run
if "sim_flash" in st.session_state:
    flash = st.session_state.pop("sim_flash")
    if flash.get("allowed"):
        st.success(f"✅ **ACCESS GRANTED:** {flash.get('detail')}")
    else:
        st.error(f"🚫 **ACCESS DENIED (403):** {flash.get('detail')}")


with st.form("rbac_simulator_form"):
    # 4 columns: 3 for inputs, 1 for the button
    sim_col1, sim_col2, sim_col3, sim_col4 = st.columns([1, 1, 2, 1])
    
    with sim_col1:
        test_role = st.selectbox("Simulate Role", ["staff", "admin", "master"], index=0)
    with sim_col2:
        test_method = st.selectbox("HTTP Method", ["GET", "POST", "PUT", "DELETE"], index=3)
    with sim_col3:
        # provide common endpoints as suggestions, but allow typing
        test_endpoint = st.selectbox(
            "API Endpoint", 
            [
                "/admin/logs", 
                "/admin/rbac/metrics", 
                "/users", 
                "/chat/sessions",
                "/crag/documents/secret.pdf"
            ]
        )
    with sim_col4:
        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
        submitted = st.form_submit_button("Test Engine", icon=":material/security:", type="primary", width="stretch")

if submitted:
    with st.spinner("Evaluating Casbin Policies..."):
        try:
            result = vm.simulate_rbac(test_role, test_endpoint, test_method)
            st.session_state["sim_flash"] = result
            st.rerun()
        except Exception as e:
            st.error(f"Simulation failed: {e}")
