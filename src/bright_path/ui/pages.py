"""Role-specific Streamlit page renderers."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Protocol
from zoneinfo import ZoneInfo

import streamlit as st

from bright_path.settings import DEMO_NOW
from bright_path.ui.api_client import ApiClientError

BANGKOK = ZoneInfo("Asia/Bangkok")
STATUSES = ("booked", "cancelled", "no_show")


class SchedulingClient(Protocol):
    def schedule(self, **filters: str) -> list[dict[str, Any]]: ...

    def lookups(self) -> dict[str, list[dict[str, str]]]: ...

    def history(self, lesson_id: str) -> list[dict[str, Any]]: ...

    def create_lesson(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    def update_lesson(self, lesson_id: str, payload: dict[str, Any]) -> dict[str, Any]: ...

    def delete_lesson(
        self,
        lesson_id: str,
        *,
        expected_version: int,
        reason: str,
    ) -> dict[str, Any]: ...


def parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(BANGKOK)


def display_datetime(value: str | None) -> str:
    if value is None:
        return "—"
    return parse_datetime(value).strftime("%a %d %b %Y, %H:%M")


def status_label(value: str) -> str:
    return value.replace("_", " ").title()


def schedule_rows(lessons: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "ID": lesson["id"],
            "Date": parse_datetime(lesson["starts_at"]).strftime("%a %d %b"),
            "Start": parse_datetime(lesson["starts_at"]).strftime("%H:%M"),
            "End": parse_datetime(lesson["ends_at"]).strftime("%H:%M"),
            "Students": ", ".join(student["name"] for student in lesson["students"]),
            "Tutor": lesson["tutor"]["name"],
            "Subject": lesson["tutor"]["subject"],
            "Room": lesson["room"]["id"],
            "Duration": f"{lesson['duration_minutes']} min",
            "Status": status_label(lesson["status"]),
            "Changed": "Yes" if lesson["version"] > 1 else "No",
            "Cancelled at": display_datetime(lesson["cancelled_at"]),
            "Note": lesson["note"] or "—",
            "Version": lesson["version"],
        }
        for lesson in lessons
    ]


def render_api_error(error: ApiClientError) -> None:
    if error.code == "stale_version":
        st.error("This lesson changed after you opened it. Refresh the page before trying again.")
    else:
        st.error(error.detail)
    for issue in error.issues:
        st.caption(f"• {issue}")


def render_schedule(client: SchedulingClient, role: str) -> None:
    title = "My schedule" if role == "tutor" else "Center schedule"
    st.header(title)
    st.caption("Current operational lesson data in Bangkok time (UTC+7).")

    lessons = client.schedule()
    if not lessons:
        st.info("There are no current lessons for this view.")
        return

    dates = [parse_datetime(lesson["starts_at"]).date() for lesson in lessons]
    with st.expander("Filter schedule"):
        from_date = st.date_input("From date", value=min(dates), key="schedule_from")
        to_date = st.date_input("To date", value=max(dates), key="schedule_to")
        selected_statuses = st.multiselect(
            "Statuses",
            options=list(STATUSES),
            default=list(STATUSES),
            format_func=status_label,
            key="schedule_statuses",
        )

    visible = [
        lesson
        for lesson in lessons
        if from_date <= parse_datetime(lesson["starts_at"]).date() <= to_date
        and lesson["status"] in selected_statuses
    ]
    if not visible:
        st.info("No lessons match these filters.")
        return

    total, booked, cancelled, changed = st.columns(4)
    total.metric("Visible lessons", len(visible))
    booked.metric("Booked", sum(item["status"] == "booked" for item in visible))
    cancelled.metric("Cancelled", sum(item["status"] == "cancelled" for item in visible))
    changed.metric("Changed", sum(item["version"] > 1 for item in visible))

    st.dataframe(schedule_rows(visible), use_container_width=True, hide_index=True)
    if role == "tutor":
        st.caption(
            "Changed means the lesson was revised. Visibility here does not mean a tutor has "
            "acknowledged or read the change."
        )

    st.subheader("Lesson detail")
    chosen_id = st.selectbox(
        "Choose a lesson",
        options=[lesson["id"] for lesson in visible],
        format_func=lambda lesson_id: _lesson_option(visible, lesson_id),
        key="schedule_lesson_detail",
    )
    lesson = next(item for item in visible if item["id"] == chosen_id)
    render_lesson_detail(client, lesson)


def render_lesson_detail(client: SchedulingClient, lesson: dict[str, Any]) -> None:
    st.markdown(f"**{lesson['id']} · {status_label(lesson['status'])}**")
    st.write(
        f"{display_datetime(lesson['starts_at'])}–"
        f"{parse_datetime(lesson['ends_at']).strftime('%H:%M')} · "
        f"{lesson['duration_minutes']} minutes"
    )
    st.write(
        f"**Students:** {', '.join(student['name'] for student in lesson['students'])}  \n"
        f"**Tutor:** {lesson['tutor']['name']} ({lesson['tutor']['subject']})  \n"
        f"**Room:** {lesson['room']['id']}  \n"
        f"**Version:** {lesson['version']}"
    )
    st.write(f"**Cancelled at:** {display_datetime(lesson['cancelled_at'])}")
    st.write(f"**Note:** {lesson['note'] or '—'}")

    with st.expander("Revision history"):
        history = client.history(lesson["id"])
        if not history:
            st.caption("No application changes have been recorded for this imported lesson.")
        for revision in reversed(history):
            st.markdown(
                f"**{display_datetime(revision['changed_at'])}** · "
                f"{revision['reason']} · {revision['changed_by']}"
            )
            st.code(
                json.dumps(
                    {"before": revision["before"], "after": revision["after"]},
                    ensure_ascii=False,
                    indent=2,
                ),
                language="json",
            )


def render_directory(lookups: dict[str, list[dict[str, str]]], role: str) -> None:
    st.header("People and rooms")
    if role == "tutor":
        st.caption("Only people and rooms connected to your schedule are shown.")
    else:
        st.caption("Current reference data available to the scheduling team.")

    st.subheader("Tutors")
    tutor_rows = [
        {
            "ID": tutor["id"],
            "Name": tutor["name"],
            "Subject": tutor["subject"],
            "Phone": tutor["phone"],
        }
        for tutor in lookups["tutors"]
    ]
    st.dataframe(tutor_rows, use_container_width=True, hide_index=True)

    st.subheader("Students")
    st.dataframe(
        [{"ID": item["id"], "Name": item["name"]} for item in lookups["students"]],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Rooms")
    st.dataframe(
        [{"Room": room["id"]} for room in lookups["rooms"]],
        use_container_width=True,
        hide_index=True,
    )
    st.caption("Only rooms observed in the supplied spreadsheet are listed.")


def render_manage(
    client: SchedulingClient,
    lookups: dict[str, list[dict[str, str]]],
) -> None:
    st.header("Manage lessons")
    st.caption("Receptionist access · every change needs a reason and is recorded.")
    lessons = client.schedule()
    create_tab, edit_tab, remove_tab = st.tabs(["Create", "Edit", "Remove"])

    with create_tab:
        submitted, payload = _lesson_form("create", lookups)
        if submitted:
            try:
                created = client.create_lesson(payload)
            except ApiClientError as error:
                render_api_error(error)
            else:
                _set_flash(f"Lesson {created['id']} was created.")
                st.rerun()

    if not lessons:
        with edit_tab:
            st.info("There are no current lessons to edit.")
        with remove_tab:
            st.info("There are no current lessons to remove.")
        return

    with edit_tab:
        edit_id = st.selectbox(
            "Lesson to edit",
            options=[lesson["id"] for lesson in lessons],
            format_func=lambda lesson_id: _lesson_option(lessons, lesson_id),
            key="edit_lesson_id",
        )
        current = next(item for item in lessons if item["id"] == edit_id)
        submitted, payload = _lesson_form("edit", lookups, initial=current)
        if submitted:
            payload["expected_version"] = current["version"]
            try:
                updated = client.update_lesson(edit_id, payload)
            except ApiClientError as error:
                render_api_error(error)
            else:
                _set_flash(f"Lesson {updated['id']} was updated to version {updated['version']}.")
                st.rerun()

    with remove_tab:
        remove_id = st.selectbox(
            "Lesson to remove",
            options=[lesson["id"] for lesson in lessons],
            format_func=lambda lesson_id: _lesson_option(lessons, lesson_id),
            key="remove_lesson_id",
        )
        current = next(item for item in lessons if item["id"] == remove_id)
        st.warning(
            "Removing a lesson hides it from current schedules. Its record and history remain."
        )
        reason = st.text_input("Reason for removal", key="remove_reason")
        confirmed = st.checkbox(
            f"I confirm that lesson {remove_id} should be removed",
            key="remove_confirmed",
        )
        if st.button(
            "Remove lesson",
            type="primary",
            disabled=not confirmed or not reason.strip(),
        ):
            try:
                removed = client.delete_lesson(
                    remove_id,
                    expected_version=current["version"],
                    reason=reason,
                )
            except ApiClientError as error:
                render_api_error(error)
            else:
                _set_flash(f"Lesson {removed['id']} was removed from current schedules.")
                st.rerun()


def render_flash() -> None:
    message = st.session_state.pop("flash_message", None)
    if message:
        st.success(message)


def _set_flash(message: str) -> None:
    st.session_state["flash_message"] = message


def _lesson_form(
    prefix: str,
    lookups: dict[str, list[dict[str, str]]],
    *,
    initial: dict[str, Any] | None = None,
) -> tuple[bool, dict[str, Any]]:
    start = parse_datetime(initial["starts_at"]) if initial else parse_datetime(DEMO_NOW)
    cancellation = (
        parse_datetime(initial["cancelled_at"])
        if initial and initial["cancelled_at"]
        else start
    )
    tutor_ids = [tutor["id"] for tutor in lookups["tutors"]]
    room_ids = [room["id"] for room in lookups["rooms"]]
    student_ids = [student["id"] for student in lookups["students"]]
    selected_students = (
        [student["id"] for student in initial["students"]]
        if initial
        else student_ids[:1]
    )
    tutor_names = {tutor["id"]: tutor["name"] for tutor in lookups["tutors"]}
    student_names = {student["id"]: student["name"] for student in lookups["students"]}

    with st.form(f"{prefix}_lesson_form", clear_on_submit=False):
        lesson_date = st.date_input("Lesson date", value=start.date(), key=f"{prefix}_date")
        lesson_time = st.time_input(
            "Start time",
            value=start.time().replace(tzinfo=None),
            key=f"{prefix}_time",
        )
        duration = st.selectbox(
            "Duration",
            options=[60, 90],
            index=[60, 90].index(initial["duration_minutes"]) if initial else 0,
            format_func=lambda minutes: f"{minutes} minutes",
            key=f"{prefix}_duration",
        )
        tutor_id = st.selectbox(
            "Tutor",
            options=tutor_ids,
            index=tutor_ids.index(initial["tutor"]["id"]) if initial else 0,
            format_func=lambda value: f"{tutor_names[value]} ({value})",
            key=f"{prefix}_tutor",
        )
        room_id = st.selectbox(
            "Room",
            options=room_ids,
            index=room_ids.index(initial["room"]["id"]) if initial else 0,
            key=f"{prefix}_room",
        )
        chosen_students = st.multiselect(
            "Students (one or two)",
            options=student_ids,
            default=selected_students,
            format_func=lambda value: student_names[value],
            max_selections=2,
            key=f"{prefix}_students",
        )
        status = st.selectbox(
            "Status",
            options=list(STATUSES),
            index=list(STATUSES).index(initial["status"]) if initial else 0,
            format_func=status_label,
            key=f"{prefix}_status",
        )
        st.caption("Cancellation time is used only when the status is Cancelled.")
        cancelled_date = st.date_input(
            "Cancellation date",
            value=cancellation.date(),
            key=f"{prefix}_cancelled_date",
        )
        cancelled_time = st.time_input(
            "Cancellation time",
            value=cancellation.time().replace(tzinfo=None),
            key=f"{prefix}_cancelled_time",
        )
        note = st.text_area(
            "Note (optional)",
            value=initial["note"] or "" if initial else "",
            key=f"{prefix}_note",
        )
        reason = st.text_input("Reason for this change", key=f"{prefix}_reason")
        submitted = st.form_submit_button(
            "Create lesson" if initial is None else "Save lesson",
            type="primary",
        )

    starts_at = datetime.combine(lesson_date, lesson_time, tzinfo=BANGKOK)
    cancelled_at = (
        datetime.combine(cancelled_date, cancelled_time, tzinfo=BANGKOK).isoformat()
        if status == "cancelled"
        else None
    )
    return submitted, {
        "starts_at": starts_at.isoformat(),
        "duration_minutes": duration,
        "tutor_id": tutor_id,
        "room_id": room_id,
        "student_ids": chosen_students,
        "status": status,
        "cancelled_at": cancelled_at,
        "note": note.strip() or None,
        "reason": reason,
    }


def _lesson_option(lessons: list[dict[str, Any]], lesson_id: str) -> str:
    lesson = next(item for item in lessons if item["id"] == lesson_id)
    students = ", ".join(student["name"] for student in lesson["students"])
    start = parse_datetime(lesson["starts_at"])
    return f"{lesson_id} · {start.strftime('%d %b %H:%M')} · {students}"
