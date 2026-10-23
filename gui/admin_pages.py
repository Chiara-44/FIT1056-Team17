"""User administration and operational reports."""
import streamlit as st
from app.schedule import ROLES
from gui.common import run_action


def show_admin_page(manager):
    st.title("Administration & reports")
    tabs = []
    if manager.can("manage_users"):
        tabs.append("Create account")
    if manager.can("run_reports"):
        tabs.append("Reports")
    if not tabs:
        st.warning("Your role does not have access to administration tools.")
        return
    rendered_tabs = st.tabs(tabs)
    i = 0
    if manager.can("manage_users"):
        with rendered_tabs[i]:
            with st.form("create_user_form"):
                name = st.text_input("Full name")
                username = st.text_input("Username")
                password = st.text_input("Temporary password (min 6 characters)", type="password")
                role = st.selectbox("Role to create", ["volunteer", "staff", "admin"])
                submitted = st.form_submit_button("Create account", type="primary")
            if submitted:
                result = run_action(lambda: manager.add_user(name, username, password, role), "Account created.")
                if result:
                    st.write(f"Created {result.role} account for {result.username}.")
        i += 1
    if manager.can("run_reports"):
        with rendered_tabs[i]:
            report_type = st.selectbox("Report", ["stock", "expiry", "shortages", "donations", "hampers"])
            if st.button("Generate report", type="primary"):
                report = run_action(lambda: manager.generate_report(report_type))
                if report is not None:
                    if isinstance(report, list):
                        if report:
                            st.dataframe(report, use_container_width=True, hide_index=True)
                        else:
                            st.info("This report has no records.")
                    else:
                        st.json(report)
