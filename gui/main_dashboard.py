"""Streamlit entry point for FoodShare Tracker."""
import os
import sys

# Streamlit only adds the gui folder to the import path, so add the project folder
# as well. This lets "from app..." and "from gui..." work however the app is started.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from app.schedule import ScheduleManager, ROLES


def get_manager():
    if "manager" not in st.session_state:
        st.session_state.manager = ScheduleManager()
    return st.session_state.manager


def show_first_admin_setup(manager):
    st.title("FoodShare Tracker")
    st.subheader("First-time setup")
    st.info("Create the first administrator account to set up the system.")
    with st.form("first_admin_form"):
        name = st.text_input("Full name")
        username = st.text_input("Username")
        password = st.text_input("Password (at least 6 characters)", type="password")
        confirm = st.text_input("Confirm password", type="password")
        submitted = st.form_submit_button("Create administrator", type="primary")
    if submitted:
        if password != confirm:
            st.error("The passwords do not match.")
            return
        try:
            manager.add_user(name, username, password, "admin")
            st.success("Administrator account created. You can now log in.")
            st.rerun()
        except (ValueError, PermissionError) as exc:
            st.error(str(exc))


def show_login(manager):
    st.title("FoodShare Tracker")
    st.write("Sign in to manage food donations, client hampers and pickups.")
    with st.form("login_form"):
        role = st.selectbox("Role", ROLES)
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log in", type="primary")
    if submitted:
        user = manager.login(username.strip(), password, role)
        if user:
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.session_state.logged_in = False
            st.error("Those login details don't match the selected role.")


def launch():
    st.set_page_config(page_title="FoodShare Tracker", page_icon="🥫", layout="wide")
    manager = get_manager()

    if manager.needs_setup():
        show_first_admin_setup(manager)
        return

    if manager.session_expired():
        manager.logout()
        st.session_state.logged_in = False
        st.warning("You were logged out after 10 minutes without activity. Please log in again.")

    if not st.session_state.get("logged_in") or manager.current_user is None:
        show_login(manager)
        return

    from gui.client_pages import show_client_page
    from gui.inventory_pages import show_inventory_page
    from gui.hamper_pages import show_hamper_page
    from gui.pickup_pages import show_pickup_page
    from gui.task_pages import show_task_page
    from gui.admin_pages import show_admin_page

    user = manager.current_user
    st.sidebar.title("FoodShare Tracker")
    st.sidebar.write(f"Signed in as **{user.name}**")
    st.sidebar.caption(f"Role: {user.role.title()}")

    pages = {"Dashboard": None}
    if manager.can("manage_clients"):
        pages["Clients"] = show_client_page
    else:
        # Volunteers can see the minimum client information needed for packing.
        pages["Client packing information"] = show_client_page
    if manager.can("manage_inventory") or manager.can("report_stock"):
        pages["Inventory & donations"] = show_inventory_page
    if manager.can("pack_hamper") or manager.can("create_hamper"):
        pages["Prepare hampers"] = show_hamper_page
    if manager.can("record_pickup") or manager.can("manage_pickups"):
        pages["Pickups"] = show_pickup_page
    if manager.can("view_own_tasks") or manager.can("manage_tasks"):
        pages["Volunteer tasks"] = show_task_page
    if manager.can("manage_users") or manager.can("run_reports"):
        pages["Admin & reports"] = show_admin_page

    selected = st.sidebar.radio("Navigation", list(pages.keys()))
    if st.sidebar.button("Log out", use_container_width=True):
        manager.logout()
        st.session_state.logged_in = False
        st.rerun()

    if selected == "Dashboard":
        st.title("FoodShare Tracker")
        st.subheader(f"Welcome, {user.name}")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Clients", len(manager.clients))
        c2.metric("Stock items", len(manager.storeroom))
        c3.metric("Hampers", len(manager.hampers))
        c4.metric("Pickups", len(manager.pickups))
        st.markdown("Use the navigation menu to open the tasks available to your role.")
        if user.role == "volunteer":
            st.info("Only the minimum client information needed for safe packing is shown to volunteers.")
    else:
        pages[selected](manager)


if __name__ == "__main__":
    launch()
