"""Shared helpers for FoodShare Tracker Streamlit pages."""
import streamlit as st


def run_action(action, success_message=None):
    """Run a backend action and show readable validation/permission errors."""
    try:
        result = action()
        if success_message:
            st.success(success_message)
        return result
    except (ValueError, PermissionError, NotImplementedError) as exc:
        st.error(str(exc))
    except Exception as exc:
        st.error(f"Something went wrong: {exc}")
    return None


def as_options(values):
    return list(values) if values else []


def display_client_label(client):
    return f"Client #{client.id} — {client.name}"


def display_item_label(item):
    return f"#{item.id} — {item.name} (stock: {item.quantity})"


def display_hamper_label(hamper):
    return f"Hamper #{hamper.id} — Client #{hamper.client_id} — {hamper.status}"
