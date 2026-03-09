import streamlit as st
import pandas as pd
from mvvm.services.api_client import ApiClient
from mvvm.viewmodels.logs_vm import LogsViewModel

st.set_page_config(page_title="System Logs", page_icon="📡", layout="wide")

st.title("System Logs")
st.markdown("View all backend server crashes, warnings, and error traces. **Master use only.**")

if "user" not in st.session_state or st.session_state.user.get("role") != "master":
    st.error("You do not have permission to view System Logs.")
    st.stop()

token = st.session_state.get("token")
api = ApiClient(base_url="http://localhost:8000", token=token)
vm = LogsViewModel(api)

col1, col2 = st.columns([0.8, 0.2])
with col2:
    if st.button("Clear Logs", icon=":material/delete_sweep:", width="stretch", type="primary"):
        vm.clear_system_logs()
        st.success("Logs cleared.")
        st.rerun()

with st.spinner("Fetching logs..."):
    try:
        logs = vm.get_system_logs()
    except Exception as e:
        st.error(f"Error fetching logs: {e}")
        st.stop()

if not logs:
    st.info("No system errors have been logged yet. Everything is running smoothly!")
    st.stop()

df = pd.DataFrame(logs)

# Filter by Level
level_filter = col1.selectbox("Filter by Level", ["All Levels", "ERROR", "WARNING", "INFO"])
if level_filter != "All Levels":
    df = df[df["level"] == level_filter]

st.subheader(f"Recent Events ({len(df)})")

# Iterate through logs and display as grouped expanders for readability
for idx, row in df.iterrows():
    icon = "🔴" if row["level"] == "ERROR" else "🟡" if row["level"] == "WARNING" else "🔵"
    timestamp_str = row["timestamp"][:16].replace("T", " ") # Format: YYYY-MM-DD HH:MM
    
    # Expandable header: Time + Endpoint + Snip of the error
    expander_title = f"{icon} **{timestamp_str}** | `{row['endpoint']}` | {row['error_message'][:60]}..."
    
    with st.expander(expander_title):
        st.markdown(f"**Error Message:** `{row['error_message']}`")
        
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**Endpoint Triggered:** `{row['endpoint']}`")
            st.markdown(f"**User:** `{row['username']}`")
        with c2:
            st.markdown("**Request Payload:**")
            if row["request_payload"]:
                st.code(row["request_payload"], language="json")
            else:
                st.write("*(No valid JSON payload recorded)*")
                
        st.markdown("**Stack Trace:**")
        if row["traceback"]:
            st.code(row["traceback"], language="python")
        else:
            st.write("*(No stack trace recorded)*")
