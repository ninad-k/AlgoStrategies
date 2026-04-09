"""Core drawing logic: create, list, inspect, and remove chart shapes."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from ..connection import evaluate, get_chart_api


async def draw_shape(
    *,
    shape: str,
    point: dict[str, Any],
    point2: dict[str, Any] | None = None,
    overrides: str | None = None,
    text: str | None = None,
) -> dict[str, Any]:
    """Create a new drawing (hline, trend line, rect, text) on the chart."""
    parsed_overrides = json.loads(overrides) if overrides else {}
    api_path = await get_chart_api()
    overrides_str = json.dumps(parsed_overrides)
    text_str = json.dumps(text) if text else '""'

    before = await evaluate(f"{api_path}.getAllShapes().map(function(s) {{ return s.id; }})") or []

    if point2:
        await evaluate(
            f"""
            {api_path}.createMultipointShape(
              [{{ time: {point['time']}, price: {point['price']} }}, {{ time: {point2['time']}, price: {point2['price']} }}],
              {{ shape: '{shape}', overrides: {overrides_str}, text: {text_str} }}
            )
            """
        )
    else:
        await evaluate(
            f"""
            {api_path}.createShape(
              {{ time: {point['time']}, price: {point['price']} }},
              {{ shape: '{shape}', overrides: {overrides_str}, text: {text_str} }}
            )
            """
        )

    await asyncio.sleep(0.2)
    after = await evaluate(f"{api_path}.getAllShapes().map(function(s) {{ return s.id; }})") or []
    new_id = next((sid for sid in after if sid not in before), None)
    return {"success": True, "shape": shape, "entity_id": new_id}


async def list_drawings() -> dict[str, Any]:
    api_path = await get_chart_api()
    shapes = await evaluate(
        f"""
        (function() {{
          var api = {api_path};
          var all = api.getAllShapes();
          return all.map(function(s) {{ return {{ id: s.id, name: s.name }}; }});
        }})()
        """
    ) or []
    return {"success": True, "count": len(shapes), "shapes": shapes}


async def get_properties(*, entity_id: str) -> dict[str, Any]:
    api_path = await get_chart_api()
    safe_id = entity_id.replace("'", "\\'")
    result = await evaluate(
        f"""
        (function() {{
          var api = {api_path};
          var eid = '{safe_id}';
          var props = {{ entity_id: eid }};
          var shape = api.getShapeById(eid);
          if (!shape) return {{ error: 'Shape not found: ' + eid }};
          try {{ var pts = shape.getPoints(); if (pts) props.points = pts; }} catch(e) {{ props.points_error = e.message; }}
          try {{ var ovr = shape.getProperties(); if (ovr) props.properties = ovr; }} catch(e) {{
            try {{ var ovr2 = shape.properties(); if (ovr2) props.properties = ovr2; }} catch(e2) {{ props.properties_error = e2.message; }}
          }}
          try {{ props.visible = shape.isVisible(); }} catch(e) {{}}
          try {{ props.locked = shape.isLocked(); }} catch(e) {{}}
          try {{
            var all = api.getAllShapes();
            for (var i = 0; i < all.length; i++) {{ if (all[i].id === eid) {{ props.name = all[i].name; break; }} }}
          }} catch(e) {{}}
          return props;
        }})()
        """
    )
    if result and result.get("error"):
        raise RuntimeError(result["error"])
    return {"success": True, **(result or {})}


async def remove_one(*, entity_id: str) -> dict[str, Any]:
    api_path = await get_chart_api()
    safe_id = entity_id.replace("'", "\\'")
    result = await evaluate(
        f"""
        (function() {{
          var api = {api_path};
          var eid = '{safe_id}';
          var before = api.getAllShapes();
          var found = false;
          for (var i = 0; i < before.length; i++) {{ if (before[i].id === eid) {{ found = true; break; }} }}
          if (!found) return {{ removed: false, error: 'Shape not found: ' + eid }};
          api.removeEntity(eid);
          var after = api.getAllShapes();
          var stillExists = false;
          for (var j = 0; j < after.length; j++) {{ if (after[j].id === eid) {{ stillExists = true; break; }} }}
          return {{ removed: !stillExists, entity_id: eid, remaining_shapes: after.length }};
        }})()
        """
    )
    if result and result.get("error"):
        raise RuntimeError(result["error"])
    return {"success": True, **(result or {})}


async def clear_all() -> dict[str, Any]:
    api_path = await get_chart_api()
    await evaluate(f"{api_path}.removeAllShapes()")
    return {"success": True, "action": "all_shapes_removed"}
