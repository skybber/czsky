"""MCP resources: static reference data the model can read instead of calling tools."""

from __future__ import annotations

import json
from typing import Any, Callable

DSO_TYPES = {
    "GX": "Galaxy",
    "GALCL": "Galaxy cluster",
    "GC": "Globular cluster",
    "OC": "Open cluster",
    "BN": "Bright (emission/reflection) nebula",
    "HII": "HII region",
    "RNe": "Reflection nebula",
    "PN": "Planetary nebula",
    "DN": "Dark nebula",
    "QSO": "Quasar",
    "AST": "Asterism",
    "STARS": "Star group",
    "PartOf": "Part of another object",
}

OBJECT_ID_FORMATS = {
    "dso:<id>": "Deep-sky object",
    "double_star:<id>": "Double star",
    "comet:<id>": "Comet",
    "minor_planet:<id>": "Minor planet",
    "planet:<id>": "Planet",
    "planet_moon:<id>": "Planet moon",
}


def register_resources(server: Any, *, get_app: Callable[[], Any]) -> None:
    @server.resource(
        "czsky://reference/dso-types",
        name="dso-types",
        description="Deep-sky object type codes used in results and in the dso_type filter.",
        mime_type="application/json",
    )
    def dso_types() -> str:
        return json.dumps(DSO_TYPES)

    @server.resource(
        "czsky://reference/object-ids",
        name="object-ids",
        description="Formats of objectId values accepted by tools (object_id parameter).",
        mime_type="application/json",
    )
    def object_ids() -> str:
        return json.dumps(OBJECT_ID_FORMATS)

    @server.resource(
        "czsky://reference/constellations",
        name="constellations",
        description="IAU constellation codes and names with their observing season.",
        mime_type="application/json",
    )
    def constellations() -> str:
        from app.models import Constellation

        with get_app().app_context():
            rows = Constellation.query.order_by(Constellation.iau_code.asc()).all()
            return json.dumps([
                {"iauCode": row.iau_code, "name": row.name, "season": row.season} for row in rows
            ])

    @server.resource(
        "czsky://reference/catalogues",
        name="catalogues",
        description="Deep-sky catalogue codes usable as obj_source in dso.find.",
        mime_type="application/json",
    )
    def catalogues() -> str:
        from app.models import Catalogue

        with get_app().app_context():
            rows = Catalogue.query.order_by(Catalogue.code.asc()).all()
            return json.dumps([{"code": row.code, "name": row.name} for row in rows])

    @server.resource(
        "czsky://reference/dso-lists",
        name="dso-lists",
        description="Observing lists (Messier, Caldwell, ...) usable in dso.find and dso_list.progress.",
        mime_type="application/json",
    )
    def dso_lists() -> str:
        from app.models import DsoList

        with get_app().app_context():
            rows = DsoList.query.filter(DsoList.hidden.is_(False)).order_by(DsoList.name.asc()).all()
            return json.dumps([
                {"dsoListId": row.id, "name": row.name, "longName": row.long_name} for row in rows
            ])
