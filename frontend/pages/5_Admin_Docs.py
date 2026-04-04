import streamlit as st
import time
from mvvm.services.api_client import ApiClient
from mvvm.viewmodels.docs_vm import DocsViewModel
from mvvm.viewmodels.users_vm import UsersViewModel

# auth & admin guard
st.set_page_config(page_title="Admin Docs", page_icon=":material/admin_panel_settings:")

token = st.session_state.get("token")
user = st.session_state.get("user")

if not token or not user:
    st.warning("Please log in first.")
    st.switch_page("pages/0_Login.py")
    st.stop()

# simple master password check
if "admin_unlocked" not in st.session_state:
    st.session_state["admin_unlocked"] = False

if not st.session_state["admin_unlocked"]:
    st.title("Admin Access Required")
    st.caption("This area is restricted to Master/Admin users.")

    with st.form("admin_login"):
        pwd = st.text_input("Enter Master Password", type="password")
        submitted = st.form_submit_button("Unlock", icon=":material/lock_open:")

        if submitted:
            if pwd == "Docs123":  # TODO: Move to env var or real RBAC
                st.session_state["admin_unlocked"] = True
                st.rerun()
            else:
                st.error("Incorrect password.")
    st.stop()

# mvvm setup
base_url = st.session_state.get("api_base_url", "http://127.0.0.1:8000")
try:
    api = ApiClient(base_url=base_url, token=token)
    vm = DocsViewModel(api)
    users_vm = UsersViewModel(api)
except Exception as e:
    st.error(f"Failed to connect to backend: {e}")
    st.stop()

# ui
st.title("Document Management")
st.caption("Manage the knowledge base. Use the Access button to control which staff can see each document.")

col1, col2 = st.columns([0.8, 0.2])
if col2.button("Refresh", icon=":material/refresh:", width="stretch"):
    st.rerun()

# --- upload section ---
with st.expander("Upload Document", expanded=True, icon=":material/upload_file:"):
    st.caption("Upload a PDF or TXT file to add it to the knowledge base.")
    uploaded = st.file_uploader("Upload PDF/TXT", type=["pdf", "txt"], label_visibility="collapsed", key="admin_upload")
    if uploaded is not None:
        if st.button("Ingest File", icon=":material/play_circle:", type="primary", width="stretch"):
            with st.spinner("Ingesting document..."):
                try:
                    from mvvm.viewmodels.chat_vm import ChatViewModel
                    ingest_vm = ChatViewModel(api)
                    ingest_vm.ingest_document(uploaded)
                    st.success(f"✅ **{uploaded.name}** ingested successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to ingest: {e}")

st.divider()

# fetch all staff users for the access multiselect
try:
    all_users = users_vm.list_users()
    staff_users = [u.get("username") for u in all_users if u.get("role") == "staff"]
except Exception:
    staff_users = []

# list docs
with st.spinner("Fetching documents..."):
    try:
        files = vm.list_documents()
        files = sorted(files)
    except Exception as e:
        st.error(f"Failed to fetch documents: {e}")
        files = []

if not files:
    st.info("No documents found in the database. Upload some via the Chat page!")
else:
    # search / filter row
    sc1, sc2 = st.columns([0.7, 0.3])
    search_term = sc1.text_input(
        "Search documents",
        placeholder="Filter by filename...",
        key="admin_doc_search",
        label_visibility="collapsed",
    )
    if search_term:
        visible = [f for f in files if search_term.lower() in f.lower()]
        sc2.caption(f"Showing {len(visible)} of {len(files)} docs")
    else:
        visible = files
        sc2.caption(f"{len(files)} document(s) total")

    if not visible:
        st.warning(f"No documents match **{search_term}**.")
    else:
        # column headers
        h1, h2, h3, h4 = st.columns([0.5, 0.15, 0.2, 0.15])
        h1.markdown("**Filename**")
        h2.markdown("**Staff Access**")
        h3.markdown("**Manage Access**")
        h4.markdown("**Action**")

        for file in visible:
            c1, c2, c3, c4 = st.columns([0.5, 0.15, 0.2, 0.15])
            c1.text(file)

            # show current access count
            try:
                current_access = vm.get_access(file)
            except Exception:
                current_access = []

            if current_access:
                c2.caption(f"{len(current_access)} staff")
            else:
                c2.caption("Private")

            # manage access expander inline using session state toggle
            access_key = f"access_open_{file}"
            if c3.button("Set Access", icon=":material/manage_accounts:", key=f"acc_btn_{file}", width="stretch"):
                st.session_state[access_key] = not st.session_state.get(access_key, False)

            # delete button
            if c4.button("Delete", icon=":material/delete:", key=f"del_{file}", type="primary", width="stretch"):
                with st.spinner(f"Deleting {file}..."):
                    try:
                        vm.delete_document(file)
                        DocsViewModel(api).set_access(file, [])  # clean up access rows
                        st.toast(f"Deleted {file}", icon="✅")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to delete: {e}")

            # access panel (shown below the row when toggled)
            if st.session_state.get(access_key, False):
                with st.container(border=True):
                    st.markdown(f"**Access for:** `{file}`")
                    if not staff_users:
                        st.info("No staff users found. Create some first via Register User.")
                    else:
                        selected = st.multiselect(
                            "Assign to staff",
                            options=staff_users,
                            default=current_access,
                            key=f"ms_{file}",
                            help="Leave empty = all users can see this document",
                        )
                        scol1, scol2 = st.columns(2)
                        if scol1.button("Save", icon=":material/save:", key=f"save_{file}", type="primary", width="stretch"):
                            try:
                                vm.set_access(file, selected)
                                st.success(f"Access updated for **{file}**")
                                st.session_state[access_key] = False
                                time.sleep(0.5)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed: {e}")
                        if scol2.button("Cancel", key=f"cancel_{file}", width="stretch"):
                            st.session_state[access_key] = False
                            st.rerun()

st.divider()
if st.button("Lock Admin Mode", icon=":material/lock:"):
    st.session_state["admin_unlocked"] = False
    st.rerun()
