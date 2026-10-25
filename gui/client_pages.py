"""Client registration, lookup and safe client summaries."""
import streamlit as st
from app.clients import CONTACT_METHODS, ACCESSIBILITY_NEEDS, SEVERITIES
from app.storeroom import PREFERENCES, ALLERGENS
from gui.common import run_action, display_client_label


def _allergy_form():
    allergies = {}
    for allergen in sorted(ALLERGENS):
        severity = st.selectbox(f"Severity for {allergen}", ["None", *SEVERITIES], key=f"allergy_{allergen}")
        if severity != "None":
            allergies[allergen] = severity
    return allergies


def _note_text(note):
    """Shows a private note as '[date, author] text'."""
    return f"[{note.get('date', '-')}, {note.get('by', '-')}] {note.get('text', '')}"


def show_client_page(manager):
    full_access = manager.can("manage_clients")
    st.title("Clients" if full_access else "Client packing information")
    if not full_access:
        st.caption("For privacy, volunteer view contains only client number, first name and food requirements.")
        for client in manager.list_clients():
            st.markdown(f"**Client #{client.id} — {client.name}**")
            st.write(client.packing_summary())
            st.divider()
        return

    tab1, tab2, tab3 = st.tabs(["Register client", "Find client", "Private notes"])
    with tab1:
        st.caption("We only ask for what is needed to prepare safe, suitable food and to get in touch: "
                   "name and household size for the hamper, dietary needs and allergies for safety, "
                   "and one way to contact the client about pickups and substitutions. Language and "
                   "accessibility needs are optional. Volunteers only see the first name and food needs.")
        with st.form("add_client_form"):
            name = st.text_input("Full name *")
            phone = st.text_input("Phone")
            email = st.text_input("Email")
            contact_method = st.selectbox("Preferred contact method", [""] + list(CONTACT_METHODS))
            adults = st.number_input("Adults", min_value=0, value=1, step=1)
            children = st.number_input("Children", min_value=0, value=0, step=1)
            infants = st.number_input("Infants", min_value=0, value=0, step=1)
            preferences = st.multiselect("Dietary requirements / preferences", sorted(PREFERENCES))
            accessibility = st.multiselect("Accessibility needs", list(ACCESSIBILITY_NEEDS))
            language = st.text_input("Preferred language")
            food_notes = st.text_area("Food-related notes (not private case notes)")
            allergies = _allergy_form()
            consent = st.checkbox("The client has agreed to these details being stored")
            submitted = st.form_submit_button("Register client", type="primary")
        if submitted:
            client = run_action(
                lambda: manager.add_client(
                    name, phone, allergies, preferences, max(int(adults) + int(children) + int(infants), 1), consent=consent,
                    household={"adults": int(adults), "children": int(children), "infants": int(infants)},
                    email=email, contact_method=contact_method or None,
                    accessibility_needs=accessibility, food_notes=food_notes, language=language,
                ), "Client registered successfully.")
            if client:
                st.write(f"Client number: **{client.id}**")

    with tab2:
        if not manager.list_clients():
            st.info("No clients have been registered yet.")
        else:
            chosen = st.selectbox("Choose a client", manager.list_clients(), format_func=display_client_label)
            if chosen:
                st.subheader(f"Client #{chosen.id}: {chosen.name}")
                st.write({"Phone": chosen.phone or "—", "Email": chosen.email or "—",
                          "Contact method": chosen.contact_method or "—", "Household size": chosen.household_size,
                          "Language": chosen.language or "—"})
                st.markdown("**Packing summary**")
                st.write(chosen.packing_summary())
                if chosen.private_notes:
                    st.markdown("**Private notes**")
                    for note in chosen.private_notes:
                        st.write(_note_text(note))
                with st.expander("Edit details"):
                    with st.form(f"edit_client_{chosen.id}"):
                        new_phone = st.text_input("Phone", value=chosen.phone or "")
                        new_email = st.text_input("Email", value=chosen.email or "")
                        methods = [""] + list(CONTACT_METHODS)
                        current = chosen.contact_method if chosen.contact_method in methods else ""
                        new_method = st.selectbox("Preferred contact method", methods, index=methods.index(current))
                        new_language = st.text_input("Preferred language", value=chosen.language or "")
                        new_notes = st.text_area("Food-related notes", value=chosen.food_notes or "")
                        save = st.form_submit_button("Save changes")
                    if save:
                        updated = run_action(lambda: manager.update_client(
                            chosen.id, phone=new_phone, email=new_email,
                            contact_method=new_method or None, language=new_language,
                            food_notes=new_notes), "Client details updated.")
                        if updated:
                            st.rerun()
                with st.expander("Add private note"):
                    note_text = st.text_area("Private note", key=f"private_note_{chosen.id}")
                    if st.button("Save private note", key=f"save_note_{chosen.id}"):
                        if note_text.strip():
                            run_action(lambda: manager.add_client_note(chosen.id, note_text.strip()), "Private note saved.")
                        else:
                            st.warning("Enter a note first.")

    with tab3:
        st.warning("Private notes are visible only to staff and administrators.")
        for client in manager.list_clients():
            if client.private_notes:
                with st.expander(f"Client #{client.id} — {client.name}"):
                    for note in client.private_notes:
                        st.write(_note_text(note))
