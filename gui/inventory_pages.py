"""Inventory, donation logging and stock problem reporting."""
from datetime import date
import streamlit as st
from app.storeroom import ALLERGENS, PREFERENCES, CONDITIONS, FLAGS
from app.schedule import ADJUSTMENT_REASONS
from app.tasks import STOCK_PROBLEMS
from gui.common import run_action, display_item_label


def item_rows(items):
    """Table rows for stock items, including warning flags (FR-12)."""
    return [{"ID": item.id, "Item": item.name, "Quantity": item.quantity,
             "Expiry": item.expiry.isoformat() if item.expiry else "—",
             "Contains": ", ".join(sorted(item.allergens)) or "—",
             "May contain": ", ".join(sorted(item.may_contain)) or "—",
             "Dietary tags": ", ".join(sorted(item.preferences)) or "—",
             "Condition": item.condition,
             "Flags": ", ".join(item.flags()) or "—"} for item in items]


def show_search(manager):
    """FR-11: search and filter stock."""
    with st.form("stock_search_form"):
        text = st.text_input("Item name contains")
        exclude = st.multiselect("Leave out items with these allergens (contains or may contain)",
                                 sorted(ALLERGENS))
        suitable = st.multiselect("Must be suitable for", sorted(PREFERENCES))
        flag = st.selectbox("Only items flagged as", ["(any)"] + list(FLAGS))
        in_stock = st.checkbox("Only items in stock")
        submitted = st.form_submit_button("Search", type="primary")
    if submitted:
        filters = {"text": text, "exclude_allergens": exclude, "suitable_for": suitable,
                   "in_stock": in_stock}
        if flag != "(any)":
            filters["flag"] = flag
        results = run_action(lambda: manager.search_inventory(filters))
        if results is not None:
            st.write(f"{len(results)} item(s) found.")
            if results:
                st.dataframe(item_rows(results), use_container_width=True, hide_index=True)


def show_adjust_stock(manager):
    """FR-10, FR-12: remove damaged/discarded stock, correct counts and mark batch condition."""
    if not manager.storeroom:
        st.info("There are no stock items to adjust.")
        return
    st.subheader("Change a quantity")
    open_reports = run_action(manager.open_stock_reports) or []
    with st.form("adjust_stock_form"):
        item = st.selectbox("Item", manager.storeroom, format_func=display_item_label,
                            key="adjust_item")
        reason = st.selectbox("Reason", list(ADJUSTMENT_REASONS))
        amount = st.number_input("How many", min_value=1, value=1, step=1)
        direction = st.radio("For a count correction", ["Remove", "Add"], horizontal=True)
        note = st.text_input("Details (optional)")
        report_options = [None] + [r.id for r in open_reports]
        report_id = st.selectbox("Volunteer stock report this deals with", report_options,
                                 format_func=lambda r: "None" if r is None else f"Report #{r}")
        submitted = st.form_submit_button("Adjust stock", type="primary")
    if submitted:
        change = int(amount)
        if not (reason == "count correction" and direction == "Add"):
            change = -change
        result = run_action(lambda: manager.adjust_stock(item.id, change, reason, note, report_id),
                            "Stock updated.")
        if result:
            st.write(f"{result.name} now has {result.quantity} in stock.")
    st.subheader("Mark a batch's condition")
    with st.form("condition_form"):
        item = st.selectbox("Item", manager.storeroom, format_func=display_item_label,
                            key="condition_item")
        condition = st.selectbox("Condition", list(CONDITIONS))
        submitted = st.form_submit_button("Save condition")
    if submitted:
        run_action(lambda: manager.set_item_condition(item.id, condition),
                   f"{item.name} marked as {condition}. Damaged or contaminated stock can't be packed.")


def show_inventory_page(manager):
    st.title("Inventory & donations")
    can_manage = manager.can("manage_inventory")
    can_report = manager.can("report_stock")
    tab_names = ["Current stock", "Search"]
    if can_report:
        tab_names.append("Report a stock problem")
    if can_manage:
        tab_names.insert(1, "Record donation")
        tab_names.append("Open stock reports")
        tab_names.append("Adjust stock")
    tabs = st.tabs(tab_names)
    index = 0
    with tabs[index]:
        if not manager.storeroom:
            st.info("No stock items recorded yet.")
        else:
            flagged = [item for item in manager.storeroom if item.flags()]
            if flagged:
                st.warning(f"{len(flagged)} item(s) need attention: "
                           + ", ".join(f"{i.name} ({', '.join(i.flags())})" for i in flagged))
            st.dataframe(item_rows(manager.storeroom), use_container_width=True, hide_index=True)
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
        show_search(manager)
    index += 1
    if can_report:
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
                    st.caption("Use the Adjust stock tab to remove the stock and close a report.")
        index += 1
        with tabs[index]:
            show_adjust_stock(manager)
