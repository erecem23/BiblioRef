"""Small shared typing aliases; runtime output remains ordinary dictionaries."""

from typing import Any, Dict, Literal

Scope = Literal["all_reference_sections", "final_reference_section", "unique_references"]
Report = Dict[str, Any]
