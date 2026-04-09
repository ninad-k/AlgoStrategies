"""Core indicator settings logic: modify inputs and toggle visibility."""

from __future__ import annotations

import json
from typing import Any

from ..connection import evaluate
from ..connection.api_resolver import KNOWN_PATHS

CHART_API: str = KNOWN_PATHS["chart_api"]


async def set_inputs(*, entity_id: str, inputs: str) -> dict[str, Any]:
    """Override specific input values on an existing study."""
    if not entity_id:
        raise ValueError("entity_id is required. Use chart_get_state to find study IDs.")
    parsed = json.loads(inputs) if isinstance(inputs, str) else inputs
    if not parsed or not isinstance(parsed, dict) or len(parsed) == 0:
        raise ValueError('inputs must be a non-empty object, e.g. { "length": 50 }')

    safe_id = entity_id.replace("'", "\\'")
    inputs_json = json.dumps(parsed)

    result = await evaluate(
        f"""
        (function() {{
          var chart = {CHART_API};
          var study = chart.getStudyById('{safe_id}');
          if (!study) return {{ error: 'Study not found: {safe_id}' }};
          var currentInputs = study.getInputValues();
          var overrides = {inputs_json};
          var updatedKeys = {{}};
          for (var i = 0; i < currentInputs.length; i++) {{
            if (overrides.hasOwnProperty(currentInputs[i].id)) {{
              currentInputs[i].value = overrides[currentInputs[i].id];
              updatedKeys[currentInputs[i].id] = overrides[currentInputs[i].id];
            }}
          }}
          study.setInputValues(currentInputs);
          return {{ updated_inputs: updatedKeys }};
        }})()
        """
    )
    if result and result.get("error"):
        raise RuntimeError(result["error"])
    return {"success": True, "entity_id": entity_id, "updated_inputs": (result or {}).get("updated_inputs")}


async def toggle_visibility(*, entity_id: str, visible: bool) -> dict[str, Any]:
    """Show or hide a study on the chart."""
    if not entity_id:
        raise ValueError("entity_id is required. Use chart_get_state to find study IDs.")

    safe_id = entity_id.replace("'", "\\'")
    result = await evaluate(
        f"""
        (function() {{
          var chart = {CHART_API};
          var study = chart.getStudyById('{safe_id}');
          if (!study) return {{ error: 'Study not found: {safe_id}' }};
          study.setVisible({'true' if visible else 'false'});
          var actualVisible = study.isVisible();
          return {{ visible: actualVisible }};
        }})()
        """
    )
    if result and result.get("error"):
        raise RuntimeError(result["error"])
    return {"success": True, "entity_id": entity_id, "visible": (result or {}).get("visible")}
