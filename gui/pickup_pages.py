"""Pickup scheduling and collection."""
from datetime import date, datetime, time
import streamlit as st
from gui.common import run_action


def show_pickup_page(manager):
    st.title("Pickups")
    can_manage = manager.can("manage_pickups")
    can_record = manager.can("record_pickup")
    tab_names = ["Daily pickup list"]
    if can_manage:
        tab_names.append("Schedule a pickup")
    if can_manage:
        tab_names.append("Reschedule / cancel")
    tabs = st.tabs(tab_names)
    with tabs[0]:
        day = st.date_input("Pickup date", value=date.today(), key="pickup_day")
        pickups = run_action(lambda: manager.pickups_on(day))
        if pickups is not None:
            if not pickups:
                st.info("No pickups scheduled for this date.")
            for pickup in pickups:
                st.write(manager.pickup_label(pickup))
                if can_record and pickup.status == "scheduled":
                    if st.button("Mark collected", key=f"collect_{pickup.id}"):
                        result = run_action(lambda: manager.record_collection(pickup.id), "Pickup marked as collected.")
                        if result:
                            st.rerun()
                st.divider()
    if can_manage:
        with tabs[1]:
            completed = [h for h in manager.hampers if h.status == "completed"]
            active_hamper_ids = {p.hamper_id for p in manager.pickups if p.status != "cancelled"}
            eligible = [h for h in completed if h.id not in active_hamper_ids]
            if not eligible:
                st.info("Complete a hamper before scheduling its pickup.")
            else:
                with st.form("schedule_pickup_form"):
                    hamper = st.selectbox("Completed hamper", eligible,
                                          format_func=lambda h: f"Hamper #{h.id} — Client #{h.client_id}")
                    pickup_date = st.date_input("Date", value=date.today(), min_value=date.today())
                    pickup_time = st.time_input("Time", value=time(10, 0))
                    submitted = st.form_submit_button("Schedule pickup", type="primary")
                if submitted:
                    when = datetime.combine(pickup_date, pickup_time)
                    result = run_action(lambda: manager.schedule_pickup(hamper.id, when), "Pickup scheduled.")
                    if result:
                        st.write(f"Pickup number: {result.id}")
    if can_manage:
        with tabs[2]:
            active = [p for p in manager.pickups if p.status == "scheduled"]
            if not active:
                st.info("There are no scheduled pickups to change.")
            else:
                pickup = st.selectbox("Scheduled pickup", active,
                                      format_func=lambda p: f"Pickup #{p.id} — {p.scheduled_at.strftime('%Y-%m-%d %H:%M')}")
                new_date = st.date_input("New date", value=max(date.today(), pickup.scheduled_at.date()), key="reschedule_date")
                new_time = st.time_input("New time", value=pickup.scheduled_at.time().replace(second=0, microsecond=0), key="reschedule_time")
                if st.button("Save new pickup time"):
                    result = run_action(lambda: manager.reschedule_pickup(pickup.id, datetime.combine(new_date, new_time)), "Pickup rescheduled.")
                    if result:
                        st.rerun()
                if st.button("Cancel this pickup", key=f"cancel_pickup_{pickup.id}"):
                    result = run_action(lambda: manager.cancel_pickup(pickup.id), "Pickup cancelled.")
                    if result:
                        st.rerun()
