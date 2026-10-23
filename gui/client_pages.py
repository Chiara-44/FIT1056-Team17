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


def show_client_page(manager):
    full_access = manager.can("manage_clients")
    st.title("Clients" if full_access else "Client packing information")
    if not full_access:
        st.caption("For privacy, volunteer view contains only client number, first name and food requirements.")
        for client in manager.clients:
            first_name = client.name.split()[0] if client.name else "Unknown"
            st.markdown(f"**Client #{client.id} — {first_name}**")
            st.write(client.packing_summary())
            st.divider()
        return

    tab1, tab2, tab3 = st.tabs(["Register client", "Find client", "Private notes"])
    with tab1:
        with st.form("add_client_form"):
            name = st.text_input("Full name *")
            phone = st.text_input("Phone")
            email = st.text_input("Email")
            contact_method = st.selectbox("Preferred contact method", [""] + list(CONTACT_METHODS))
            household_size = st.number_input("Household size", min_value=1, value=1, step=1)
            adults = st.number_input("Adults", min_value=0, value=1, step=1)
            children = st.number_input("Children", min_value=0, value=0, step=1)
            infants = st.number_input("Infants", min_value=0, value=0, step=1)
            preferences = st.multiselect("Dietary requirements / preferences", sorted(PREFERENCES))
            accessibility = st.multiselect("Accessibility needs", list(ACCESSIBILITY_NEEDS))
            language = st.text_input("Preferred language")
            food_notes = st.text_area("Food-related notes (not private case notes)")
            allergies = _allergy_form()
            submitted = st.form_submit_button("Register client", type="primary")
        if submitted:
            client = run_action(
                lambda: manager.add_client(
                    name, phone, allergies, preferences, int(household_size),
                    household={"adults": int(adults), "children": int(children), "infants": int(infants)},
                    email=email, contact_method=contact_method or None,
                    accessibility_needs=accessibility, food_notes=food_notes, language=language,
                ), "Client registered successfully.")
            if client:
                st.write(f"Client number: **{client.id}**")

    with tab2:
        if not manager.clients:
            st.info("No clients have been registered yet.")
        else:
            chosen = st.selectbox("Choose a client", manager.clients, format_func=display_client_label)
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
                        st.write(note)
                with st.expander("Add private note"):
                    note_text = st.text_area("Private note", key=f"private_note_{chosen.id}")
                    if st.button("Save private note", key=f"save_note_{chosen.id}"):
                        if note_text.strip():
                            run_action(lambda: manager.add_client_note(chosen.id, note_text.strip()), "Private note saved.")
                        else:
                            st.warning("Enter a note first.")

    with tab3:
        st.warning("Private notes are visible only to staff and administrators.")
        for client in manager.clients:
            if client.private_notes:
                with st.expander(f"Client #{client.id} — {client.name}"):
                    for note in client.private_notes:
                        st.write(note)
