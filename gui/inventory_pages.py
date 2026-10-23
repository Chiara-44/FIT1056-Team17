"""Inventory, donation logging and stock problem reporting."""
from datetime import date
import streamlit as st
from app.storeroom import ALLERGENS, PREFERENCES
from app.tasks import STOCK_PROBLEMS
from gui.common import run_action, display_item_label


def show_inventory_page(manager):
    st.title("Inventory & donations")
    can_manage = manager.can("manage_inventory")
    tab_names = ["Current stock", "Report a stock problem"]
    if can_manage:
        tab_names.insert(1, "Record donation")
        tab_names.append("Open stock reports")
    tabs = st.tabs(tab_names)
    index = 0
    with tabs[index]:
        if not manager.storeroom:
            st.info("No stock items recorded yet.")
        else:
            rows = []
            for item in manager.storeroom:
                rows.append({"ID": item.id, "Item": item.name, "Quantity": item.quantity,
                             "Expiry": item.expiry.isoformat() if item.expiry else "—",
                             "Contains": ", ".join(sorted(item.allergens)) or "—",
                             "May contain": ", ".join(sorted(item.may_contain)) or "—",
                             "Dietary tags": ", ".join(sorted(item.preferences)) or "—",
                             "Expired": "Yes" if item.is_expired() else "No"})
            st.dataframe(rows, use_container_width=True, hide_index=True)
    index += 1
    if can_manage:
        with tabs[index]:
            with st.form("donation_form"):
                name = st.text_input("Food item name *")
                quantity = st.number_input("Quantity donated", min_value=1, value=1, step=1)
                allergens = st.multiselect("Contains allergens", sorted(ALLERGENS))
                may_contain = st.multiselect("May contain traces of", sorted(ALLERGENS), key="donation_may_contain")
                preferences = st.multiselect("Suitable for", sorted(PREFERENCES))
                expiry = st.date_input("Expiry date (optional)", value=None, min_value=date.today())
                donor = st.text_input("Donor name (optional)")
                submitted = st.form_submit_button("Record donation", type="primary")
            if submitted:
                result = run_action(lambda: manager.record_donation(name, allergens, may_contain,
                                     preferences, int(quantity), expiry, donor), "Donation recorded.")
                if result:
                    st.write(f"{result.name}: now {result.quantity} in stock (item #{result.id}).")
        index += 1
    with tabs[index]:
        if not manager.storeroom:
            st.info("There are no stock items to report.")
        else:
            with st.form("stock_problem_form"):
                item = st.selectbox("Item", manager.storeroom, format_func=display_item_label)
                problem = st.selectbox("Problem", list(STOCK_PROBLEMS))
                quantity = st.number_input("Affected quantity", min_value=1, max_value=max(1, item.quantity), value=1, step=1)
                note = st.text_area("Additional details (optional)")
                submitted = st.form_submit_button("Submit stock report")
            if submitted:
                run_action(lambda: manager.report_stock_problem(item.id, problem, int(quantity), note),
                           "Stock problem reported. Stock has not been changed.")
    index += 1
    if can_manage:
        with tabs[index]:
            reports = run_action(manager.open_stock_reports)
            if reports is not None:
                if not reports:
                    st.success("No open stock reports.")
                else:
                    rows = []
                    for report in reports:
                        item = manager.find_item(report.item_id)
                        rows.append({"Report": report.id, "Item": item.name if item else report.item_id,
                                     "Problem": report.problem, "Quantity": report.quantity,
                                     "Note": report.note, "Reported by": report.reported_by})
                    st.dataframe(rows, use_container_width=True, hide_index=True)
                    st.caption("Stock adjustment is not available yet because adjust_stock() is not implemented in the backend.")
