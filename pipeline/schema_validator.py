"""A tiny, dependency-free JSON-Schema validator.

It supports exactly the keyword subset used by ``schema/atom.schema.json`` so
that the schema file stays the single source of truth for frontmatter shape
(as ``docs/ATOM_SCHEMA.md`` promises: "When the two disagree, the JSON Schema
wins"). It is deliberately not a general validator — if the schema grows a
keyword this does not understand, ``validate`` raises so the gap is loud, never
silently ignored.

Supported keywords: type, enum, const, pattern, minLength, minimum, minItems,
uniqueItems, format (date, uri), required, additionalProperties, properties,
items.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, List

_SUPPORTED = {
    "$schema", "$id", "title", "description",  # metadata, ignored
    "type", "enum", "const", "pattern", "minLength", "minimum",
    "minItems", "uniqueItems", "format", "required",
    "additionalProperties", "properties", "items",
}

# JSON type name -> Python predicate. bool is excluded from number/integer
# because in Python ``bool`` is a subclass of ``int``.
_TYPE_CHECKS = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
}


def _type_name(value: Any) -> str:
    for name, check in _TYPE_CHECKS.items():
        if name != "number" and check(value):
            return name
    return type(value).__name__


def _check_format(value: str, fmt: str, path: str, errors: List[str]) -> None:
    if fmt == "date":
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            errors.append(f"{path}: '{value}' is not a valid date (YYYY-MM-DD)")
            return
        try:
            y, m, d = (int(p) for p in value.split("-"))
            date(y, m, d)
        except ValueError:
            errors.append(f"{path}: '{value}' is not a real calendar date")
    elif fmt == "uri":
        # The schema pins the concrete scheme with its own `pattern`; here we
        # only assert it looks like an absolute URI.
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", value):
            errors.append(f"{path}: '{value}' is not an absolute URI")
    # Unknown formats are treated as annotations (no-op), per JSON Schema.


def validate(instance: Any, schema: dict, path: str = "$") -> List[str]:
    """Return a list of human-readable validation errors (empty == valid)."""
    unknown = set(schema) - _SUPPORTED
    if unknown:
        raise NotImplementedError(
            f"schema uses keywords this validator does not support: {sorted(unknown)}"
        )

    errors: List[str] = []

    # type
    if "type" in schema:
        types = schema["type"]
        types = [types] if isinstance(types, str) else types
        if not any(_TYPE_CHECKS[t](instance) for t in types):
            errors.append(
                f"{path}: expected type {types}, got {_type_name(instance)}"
            )
            return errors  # further checks assume the type matched

    # enum / const
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {instance!r} is not one of {schema['enum']}")
    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: {instance!r} must equal {schema['const']!r}")

    # string constraints
    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(f"{path}: shorter than minLength {schema['minLength']}")
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            errors.append(f"{path}: {instance!r} does not match /{schema['pattern']}/")
        if "format" in schema:
            _check_format(instance, schema["format"], path, errors)

    # number constraints
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{path}: less than minimum {schema['minimum']}")

    # array constraints
    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append(f"{path}: fewer than minItems {schema['minItems']}")
        if schema.get("uniqueItems"):
            seen, dupes = set(), set()
            for item in instance:
                key = repr(item)
                if key in seen:
                    dupes.add(key)
                seen.add(key)
            if dupes:
                errors.append(f"{path}: array items are not unique")
        if "items" in schema:
            for i, item in enumerate(instance):
                errors.extend(validate(item, schema["items"], f"{path}[{i}]"))

    # object constraints
    if isinstance(instance, dict):
        for req in schema.get("required", []):
            if req not in instance:
                errors.append(f"{path}: missing required property '{req}'")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in instance:
                if key not in props:
                    errors.append(f"{path}: unexpected property '{key}'")
        for key, subschema in props.items():
            if key in instance:
                errors.extend(validate(instance[key], subschema, f"{path}.{key}"))

    return errors
