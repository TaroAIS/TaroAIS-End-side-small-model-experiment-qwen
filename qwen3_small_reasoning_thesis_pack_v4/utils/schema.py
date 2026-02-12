from pathlib import Path

from utils.io import load_jsonl, read_json


class SchemaValidationError(ValueError):
    pass


def _get_validator(schema):
    try:
        import jsonschema
    except Exception as exc:
        return None
    return jsonschema.Draft202012Validator(schema)


def _type_ok(value, expected):
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    return True


def _manual_validate(value, schema, path="<root>"):
    expected = schema.get("type")
    if expected and not _type_ok(value, expected):
        return "expected type {} but got {} at {}".format(expected, type(value).__name__, path)

    if "enum" in schema and value not in schema.get("enum", []):
        return "value {} not in enum {} at {}".format(value, schema.get("enum", []), path)

    if isinstance(value, str):
        min_len = schema.get("minLength")
        if min_len is not None and len(value) < int(min_len):
            return "string shorter than minLength {} at {}".format(min_len, path)

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if minimum is not None and value < minimum:
            return "value smaller than minimum {} at {}".format(minimum, path)
        if maximum is not None and value > maximum:
            return "value larger than maximum {} at {}".format(maximum, path)

    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                return "missing required key '{}' at {}".format(key, path)
        props = schema.get("properties", {})
        for key, subschema in props.items():
            if key in value:
                err = _manual_validate(value[key], subschema, path=path + "/" + str(key))
                if err:
                    return err

    if isinstance(value, list):
        min_items = schema.get("minItems")
        if min_items is not None and len(value) < int(min_items):
            return "array shorter than minItems {} at {}".format(min_items, path)
        item_schema = schema.get("items")
        if item_schema:
            for i, item in enumerate(value):
                err = _manual_validate(item, item_schema, path=path + "/{}".format(i))
                if err:
                    return err

    return None


def validate_record(record, schema, context=""):
    validator = _get_validator(schema)
    if validator is not None:
        errors = sorted(validator.iter_errors(record), key=lambda e: e.path)
        if not errors:
            return
        first = errors[0]
        loc = "/".join([str(p) for p in first.path])
        prefix = "{}: ".format(context) if context else ""
        raise SchemaValidationError("{}{} at {}".format(prefix, first.message, loc or "<root>"))

    err = _manual_validate(record, schema, path="<root>")
    if err:
        prefix = "{}: ".format(context) if context else ""
        raise SchemaValidationError(prefix + err)


def validate_records(records, schema_path, context_prefix="record"):
    schema = read_json(schema_path)
    for idx, rec in enumerate(records, start=1):
        rid = rec.get("id", "") if isinstance(rec, dict) else ""
        ctx = "{}#{} id={}".format(context_prefix, idx, rid)
        validate_record(rec, schema, context=ctx)


def validate_jsonl_file(path, schema_path):
    rows = load_jsonl(path)
    validate_records(rows, schema_path, context_prefix=Path(path).name)
    return len(rows)
