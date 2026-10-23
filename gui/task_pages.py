"""Volunteer task management and progress updates."""
import streamlit as st
from app.tasks import TASK_STATUSES
from gui.common import run_action


def show_task_page(manager):
    st.title("Volunteer tasks")
    can_manage = manager.can("manage_tasks")
    if can_manage:
        create_tab, list_tab = st.tabs(["Create task", "All tasks"])
        with create_tab:
            volunteers = manager.volunteers
            with st.form("create_task_form"):
                title = st.text_input("Task title *")
                description = st.text_area("Description")
                assign_to = st.selectbox("Assign to volunteer (optional)", [""] + [v.username for v in volunteers])
                submitted = st.form_submit_button("Create task", type="primary")
            if submitted:
                result = run_action(lambda: manager.create_task(title, description, assign_to), "Task created.")
                if result:
                    st.write(f"Task number: {result.id}")
        with list_tab:
            tasks = run_action(manager.all_tasks)
            if tasks is not None:
                if not tasks:
                    st.info("No tasks have been created yet.")
                for task in tasks:
                    with st.expander(f"Task #{task.id}: {task.title} — {task.status}"):
                        st.write(task.description or "No description")
                        st.write(f"Assigned to: {task.assigned_to or 'Unassigned'}")
                        st.write(f"Created by: {task.created_by}")
                        if manager.volunteers:
                            chosen = st.selectbox("Assign / reassign", manager.volunteers,
                                                  format_func=lambda v: v.username,
                                                  key=f"assign_to_{task.id}")
                            if st.button("Save assignment", key=f"assign_{task.id}"):
                                result = run_action(lambda: manager.assign_task(task.id, chosen.username), "Task assigned.")
                                if result:
                                    st.rerun()
    else:
        tasks = run_action(manager.tasks_for_current_user)
        if tasks is None:
            return
        if not tasks:
            st.info("You don't have any tasks assigned right now.")
        for task in tasks:
            with st.expander(f"Task #{task.id}: {task.title} — {task.status}"):
                st.write(task.description or "No description")
                with st.form(f"task_progress_{task.id}"):
                    status = st.selectbox("Progress", list(TASK_STATUSES),
                                          index=list(TASK_STATUSES).index(task.status) if task.status in TASK_STATUSES else 0)
                    note = st.text_area("Progress note (optional)")
                    submitted = st.form_submit_button("Update task")
                if submitted:
                    result = run_action(lambda: manager.update_task_progress(task.id, status, note), "Task updated.")
                    if result:
                        st.rerun()
