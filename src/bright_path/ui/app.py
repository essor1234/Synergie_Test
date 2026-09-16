from __future__ import annotations

from collections.abc import Callable

import streamlit as st

from bright_path.settings import API_URL
from bright_path.ui.api_client import ApiClient, ApiClientError
from bright_path.ui.pages import (
    render_api_error,
    render_directory,
    render_flash,
    render_manage,
    render_schedule,
)

ClientFactory = Callable[[str, str, str | None], ApiClient]


def render_app(client_factory: ClientFactory = ApiClient) -> None:
    st.set_page_config(page_title="Bright Path", layout="wide")
    _apply_styles()

    st.title("Bright Path")
    st.caption("Scheduling and daily lesson operations")

    try:
        demo_lookups = client_factory(API_URL, "owner", None).lookups()
    except ApiClientError as error:
        st.error("Bright Path could not load its scheduling data.")
        render_api_error(error)
        st.info("Start the project services, then refresh this page.")
        return

    with st.sidebar:
        st.markdown("### Demo access")
        role_label = st.selectbox(
            "View as",
            options=["Owner", "Receptionist", "Tutor"],
            key="demo_role",
        )
        role = role_label.lower()
        tutor_id = None
        if role == "tutor":
            tutor_by_id = {item["id"]: item for item in demo_lookups["tutors"]}
            tutor_id = st.selectbox(
                "Tutor profile",
                options=list(tutor_by_id),
                format_func=lambda value: (
                    f"{tutor_by_id[value]['name']} · {tutor_by_id[value]['subject']}"
                ),
                key="demo_tutor_id",
            )
        st.caption("Demo role switching replaces production sign-in for this MVP.")

    client = client_factory(API_URL, role, tutor_id)
    try:
        lookups = client.lookups()
    except ApiClientError as error:
        render_api_error(error)
        return

    page_options = ["Schedule", "People and rooms"]
    if role == "receptionist":
        page_options.append("Manage lessons")

    with st.sidebar:
        st.markdown("### Navigation")
        page = st.radio("Page", page_options, label_visibility="collapsed")
        st.divider()
        access_copy = {
            "owner": "Read-only center oversight",
            "receptionist": "Center schedule and lesson management",
            "tutor": "Read-only personal schedule",
        }
        st.caption(access_copy[role])

    render_flash()
    try:
        if page == "Schedule":
            render_schedule(client, role)
        elif page == "People and rooms":
            render_directory(lookups, role)
        else:
            render_manage(client, lookups)
    except ApiClientError as error:
        render_api_error(error)


def _apply_styles() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            max-width: 1180px;
            padding-top: 2rem;
            padding-bottom: 3rem;
        }
        [data-testid="stMetric"] {
            border: 1px solid #dfe3e8;
            border-radius: 0.5rem;
            padding: 0.75rem 1rem;
            background: #ffffff;
        }
        [data-testid="stDataFrame"] {
            border: 1px solid #e3e7eb;
            border-radius: 0.5rem;
        }
        @media (max-width: 700px) {
            .block-container {
                padding: 1rem 0.8rem 2rem;
            }
            [data-testid="stHorizontalBlock"] {
                flex-wrap: wrap;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    render_app()
