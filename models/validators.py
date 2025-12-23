from typing import Dict, Any, List

# -----------------------------
# Single-instance validation
# -----------------------------
def validate_instance(data: Dict[str, Any]) -> List[str]:
    """
    Validate a single JRP instance dictionary.
    Checks required keys, types, non-negativity, and item completeness.
    Returns a list of error messages (empty if valid).
    """
    errors: List[str] = []

    # Required top-level keys
    for key in ["A", "r", "items"]:
        if key not in data:
            errors.append(f"Missing key: {key}")

    # Items must be a list
    if "items" in data and not isinstance(data["items"], list):
        errors.append("items must be a list")

    # Helper for numeric non-negative checks
    def nonneg(name: str, val: Any) -> str | None:
        if not isinstance(val, (int, float)):
            return f"{name} must be numeric"
        if val < 0:
            return f"{name} must be non-negative"
        return None

    # Validate A and r
    if "A" in data:
        e = nonneg("A", data["A"])
        if e:
            errors.append(e)
    if "r" in data:
        e = nonneg("r", data["r"])
        if e:
            errors.append(e)

    # Validate items
    if "items" in data and isinstance(data["items"], list):
        if len(data["items"]) == 0:
            errors.append("items list must be non-empty")
        for idx, it in enumerate(data["items"]):
            for k in ["id", "a", "D", "v"]:
                if k not in it:
                    errors.append(f"Item[{idx}] missing key: {k}")
            if "a" in it:
                e = nonneg(f"Item[{idx}].a", it["a"])
                if e:
                    errors.append(e)
            if "D" in it:
                e = nonneg(f"Item[{idx}].D", it["D"])
                if e:
                    errors.append(e)
            if "v" in it:
                e = nonneg(f"Item[{idx}].v", it["v"])
                if e:
                    errors.append(e)

    return errors

# -----------------------------
# Comparison mode helpers
# -----------------------------
def summarize_errors(errors: List[str]) -> str:
    """
    Convert a list of error strings into a single formatted message.
    Useful for displaying in the web UI.
    """
    if not errors:
        return "No validation errors."
    return "Validation errors:\n" + "\n".join(f"- {e}" for e in errors)

def validate_two_instances(data1: Dict[str, Any], data2: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    Validate two instances side by side for comparison mode.
    Returns a dictionary with error lists for each instance.
    """
    return {
        "instance1_errors": validate_instance(data1),
        "instance2_errors": validate_instance(data2)
    }