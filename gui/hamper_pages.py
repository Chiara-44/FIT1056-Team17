"""Safety-first hamper preparation."""
import streamlit as st
from gui.common import run_action, display_client_label, display_item_label, display_hamper_label


def show_hamper_page(manager):
    st.title("Prepare hampers")
    if not manager.clients:
        st.info("Register a client before creating a hamper.")
        return
    create_tab, draft_tab, history_tab = st.tabs(["Start a hamper", "Pack a draft", "Hamper history"])
    with create_tab:
        with st.form("create_hamper_form"):
            client = st.selectbox("Client", manager.clients, format_func=display_client_label)
            submitted = st.form_submit_button("Create draft hamper", type="primary")
        if submitted:
            hamper = run_action(lambda: manager.create_hamper(client.id), "Draft hamper created.")
            if hamper:
                st.write(f"Hamper number: **{hamper.id}**")
    drafts = [h for h in manager.hampers if h.is_draft()]
    with draft_tab:
        if not drafts:
            st.info("There are no draft hampers.")
        else:
            hamper = st.selectbox("Draft hamper", drafts, format_func=display_hamper_label)
            client = manager.find_client(hamper.client_id)
            if client:
                st.subheader(f"Client #{client.id} — {client.name.split()[0] if manager.current_user.role == 'volunteer' else client.name}")
                st.write(client.packing_summary())
                severe = client.severe_allergies()
                if severe:
                    st.error("Severe allergy warning: " + ", ".join(map(str, severe)))
                    if not hamper.allergy_acknowledged:
                        st.warning("You must acknowledge this warning before adding items or completing the hamper.")
                        if st.button("I have read the severe allergy warning", key=f"ack_{hamper.id}"):
                            result = run_action(lambda: manager.acknowledge_allergy_warning(hamper.id), "Warning acknowledged.")
                            if result is not None:
                                st.rerun()
            st.markdown("**Items currently in this hamper**")
            if not hamper.items:
                st.caption("No items added yet.")
            for item_id, quantity in hamper.items.items():
                item = manager.find_item(int(item_id))
                if item:
                    c1, c2 = st.columns([4, 1])
                    c1.write(f"{item.name} × {quantity}")
                    if c2.button("Remove 1", key=f"remove_{hamper.id}_{item.id}"):
                        run_action(lambda: manager.remove_hamper_item(hamper.id, item.id, 1), "Item removed.")
                        st.rerun()
            if client:
                st.caption(f"{hamper.total_items()} of {client.hamper_allowance} items "
                           "(every household gets the same allowance per person).")
            safe_items = manager.safe_items_for(client)
            if not safe_items:
                st.info("There are no currently available items marked safe for this client.")
            else:
                with st.form(f"add_item_{hamper.id}"):
                    item = st.selectbox("Add a safe item", safe_items, format_func=display_item_label)
                    quantity = st.number_input("Quantity", min_value=1, value=1, step=1)
                    submitted = st.form_submit_button("Add item")
                if submitted:
                    result = run_action(lambda: manager.add_hamper_item(hamper.id, item.id, int(quantity)), "Item added to draft.")
                    if result:
                        st.rerun()
            st.divider()
            st.warning("Completing a hamper deducts all included items from stock. Check every item and quantity first.")
            if st.button("Complete hamper and deduct stock", type="primary", key=f"complete_{hamper.id}"):
                result = run_action(lambda: manager.complete_hamper(hamper.id), "Hamper completed and stock updated.")
                if result:
                    st.rerun()
            if st.button("Cancel draft hamper", key=f"cancel_{hamper.id}"):
                result = run_action(lambda: manager.cancel_hamper(hamper.id), "Draft hamper cancelled; stock was not changed.")
                if result is not None:
                    st.rerun()
    with history_tab:
        if not manager.hampers:
            st.info("No hampers have been created yet.")
        else:
            rows = []
            for hamper in manager.hampers:
                client = manager.find_client(hamper.client_id)
                rows.append({"Hamper": hamper.id, "Client": hamper.client_id,
                             "Client name": client.name if client and manager.can("manage_clients") else (client.name.split()[0] if client and client.name else "Unknown"),
                             "Status": hamper.status, "Items": hamper.total_items(),
                             "Packed by": hamper.packer_username})
            st.dataframe(rows, use_container_width=True, hide_index=True)
