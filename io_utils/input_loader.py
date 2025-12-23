import json
import io
import csv
from typing import Dict, Any, Tuple, List
from models.jrp_solver import Item, JRPParams
from models.validators import validate_instance

# -----------------------------
# Core Loaders
# -----------------------------

def load_json_bytes(file_bytes: bytes) -> Dict[str, Any]:
    """Load JSON data from raw bytes."""
    text = file_bytes.decode("utf-8")
    data = json.loads(text)
    return data

def load_csv_plus_json(csv_bytes: bytes, meta_json_bytes: bytes) -> Dict[str, Any]:
    """Load items from CSV and global parameters from JSON metadata."""
    text = csv_bytes.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))
    items = []
    for row in reader:
        items.append({
            "id": str(row["id"]),
            "a": float(row["a"]),
            "D": float(row["D"]),
            "v": float(row["v"])
        })
    meta = json.loads(meta_json_bytes.decode("utf-8"))
    meta["items"] = items
    return meta

def to_params_struct(data: Dict[str, Any]) -> JRPParams:
    """Convert raw dict data into JRPParams structure."""
    items = [Item(id=it["id"], a=float(it["a"]), D=float(it["D"]), v=float(it["v"])) for it in data["items"]]
    return JRPParams(A=float(data["A"]), r=float(data["r"]), items=items)

def load_and_validate_from_json(file_bytes: bytes) -> Tuple[JRPParams, Dict[str, Any], List[str]]:
    """Load and validate a single JSON input file."""
    data = load_json_bytes(file_bytes)
    errors = validate_instance(data)
    params = to_params_struct(data) if not errors else None
    return params, data, errors

# -----------------------------
# Comparison Mode Helpers
# -----------------------------

def load_and_validate_two_jsons(file1_bytes: bytes, file2_bytes: bytes):
    """
    Load and validate two JSON input files for comparison mode.
    Returns (params, raw_data, errors) for each file.
    """
    result1 = load_and_validate_from_json(file1_bytes)
    result2 = load_and_validate_from_json(file2_bytes)
    return result1, result2

def extract_metadata(data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract basic metadata for reporting/visualization."""
    return {
        "instance_name": data.get("instance_name", "Unnamed_Instance"),
        "num_items": len(data.get("items", [])),
        "A": data.get("A"),
        "r": data.get("r")
    }

def extract_detailed_metadata(data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract richer metadata for comparison visuals."""
    items = data.get("items", [])
    total_value = sum(it["D"] * it["v"] for it in items)
    avg_minor_setup = sum(it["a"] for it in items) / len(items) if items else 0
    return {
        "instance_name": data.get("instance_name", "Unnamed_Instance"),
        "num_items": len(items),
        "A": data.get("A"),
        "r": data.get("r"),
        "total_value": total_value,
        "avg_minor_setup": avg_minor_setup,
        "item_ids": [it["id"] for it in items]
    }

# -----------------------------
# Sensitivity Analysis Helpers
# -----------------------------

def apply_sensitivity_overrides(data: Dict[str, Any], overrides: Dict[str, Any]) -> JRPParams:
    """
    Apply sensitivity analysis overrides (e.g., new A, r, or item parameters).
    Returns a new JRPParams object.
    """
    modified = json.loads(json.dumps(data))  # deep copy
    if "A" in overrides:
        modified["A"] = overrides["A"]
    if "r" in overrides:
        modified["r"] = overrides["r"]
    if "items" in overrides:
        # overrides["items"] is expected as dict keyed by item id
        for it in modified["items"]:
            if it["id"] in overrides["items"]:
                for key, val in overrides["items"][it["id"]].items():
                    it[key] = val
    return to_params_struct(modified)

# -----------------------------
# Report Prep Helpers
# -----------------------------

def prepare_report_tables(data: Dict[str, Any], solution: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepare structured tables for PDF export.
    Returns dict with input_table and results_table.
    """
    input_table = [
        {"Item": it["id"], "Minor Setup Cost": it["a"], "Demand Rate": it["D"], "Unit Cost": it["v"]}
        for it in data["items"]
    ]
    results_table = [
        {"Item": res["id"], "m": res["m"], "Cycle Time": res["cycle_time"],
         "Avg Inventory": res["avg_inventory"], "Holding Cost": res["annual_holding_cost"],
         "Setup Cost": res["annual_setup_cost"]}
        for res in solution.get("items", [])
    ]
    return {"input_table": input_table, "results_table": results_table}