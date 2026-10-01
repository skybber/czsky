"""MCP prompts: ready-made observing workflows composed from CzSkY tools."""

from __future__ import annotations

from typing import Any


def register_prompts(server: Any) -> None:
    @server.prompt(
        name="plan_night",
        title="Plan an observing night",
        description="Check conditions of a night and build a session plan with well placed targets.",
    )
    def plan_night(date: str = "", location: str = "", focus: str = "") -> str:
        night = f"the night of {date}" if date else "tonight"
        place = f"location '{location}'" if location else "my usual location (location.find without arguments)"
        focus_text = f" Focus on: {focus}." if focus else ""
        return (
            f"Plan an observing session for {night} at {place}.{focus_text}\n"
            "1. Call night.info to get the dark window, Moon phase and moonless hours.\n"
            "2. Find a session plan for that date (session_plan.get_id_by_date) or create one (session_plan.create).\n"
            "3. Pick targets with dso.find (session_plan_id set, not_observed=true); prefer objects that transit "
            "inside the dark window. Avoid faint galaxies when the Moon is bright and up.\n"
            "4. Optionally add bright comets (comet.list_bright) or planets (planet.positions).\n"
            "5. Add the chosen objects with session_plan.add_items and show session_plan.schedule.\n"
            "Summarize the night conditions and the schedule with transit times."
        )

    @server.prompt(
        name="log_observations",
        title="Log observations from notes",
        description="Turn free-form observing notes into observation log entries of an observing session.",
    )
    def log_observations(notes: str, date: str = "") -> str:
        when = f" from {date}" if date else ""
        return (
            f"Log these observing notes{when} into CzSkY:\n\n{notes}\n\n"
            "1. Find the observing session (observing_session.get_active or observing_session.list); "
            "if none matches, ask before creating one with observing_session.create.\n"
            "2. Load my equipment with equipment.list to map telescope/eyepiece/filter names to ids.\n"
            "3. For each observed object call observation_log.upsert with its notes, time and equipment.\n"
            "Report what was logged and anything that could not be matched."
        )

    @server.prompt(
        name="catalogue_progress",
        title="Continue an observing list",
        description="Show progress in an observing list and suggest missing objects visible on a given night.",
    )
    def catalogue_progress(dso_list: str = "Messier", date: str = "", location: str = "") -> str:
        night = f"the night of {date}" if date else "tonight"
        place = f" at '{location}'" if location else ""
        return (
            f"Show my progress in the '{dso_list}' list with dso_list.progress (include missing objects).\n"
            f"Then check which missing objects are well placed {night}{place} using visibility.get "
            "(or dso.find with obj_source=dso_list:<id> and a session plan) and suggest the best ones."
        )
