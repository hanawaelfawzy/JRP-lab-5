from dataclasses import dataclass
from typing import List, Dict, Any, Tuple
import math

@dataclass
class Item:
    id: str
    a: float      # minor setup cost
    D: float      # demand rate (units/time)
    v: float      # unit value

@dataclass
class JRPParams:
    A: float      # major setup cost
    r: float      # carrying charge ($/$ per unit time)
    items: List[Item]

# -----------------------------
# HELPER: Cost breakdown (Lecture TRC)
# -----------------------------
def total_cost(A: float, r: float, items: List[Item], T: float, m_list: List[int]) -> Dict[str, float]:
    # Lecture TRC: (A + Σ ai/mi)/T + Σ (Di * mi * T * vi * r)/2
    group_over_T = (A + sum(it.a / m for it, m in zip(items, m_list))) / T
    holding_sum = sum((it.D * m * T * it.v * r) / 2.0 for it, m in zip(items, m_list))

    # For breakdown reporting
    family_setup = A / T
    item_setup = sum(it.a / (m * T) for it, m in zip(items, m_list))

    return {
        "total": group_over_T + holding_sum,
        "family_setup": family_setup,
        "item_setup": item_setup,
        "holding": holding_sum
    }

# -----------------------------
# HELPER: Per-item metrics
# -----------------------------
def compute_item_metrics(items: List[Item], T_star: float, m_list: List[int], r: float) -> List[Dict[str, Any]]:
    results = []
    for it, m in zip(items, m_list):
        DiVi = it.D * it.v                  # dollar usage rate
        Qivi = DiVi * m * T_star            # replenishment dollar quantity per cycle
        cycle_time = m * T_star             # cycle length for this item
        avg_inventory = Qivi / (2 * it.v)   # average units held

        # Costs
        annual_holding_cost = avg_inventory * it.v * r
        annual_setup_cost = it.a / (m * T_star)

        results.append({
            "id": it.id,
            "DiVi": DiVi,
            "m": m,
            "T_star": T_star,
            "Qivi": Qivi,
            "cycle_time": cycle_time,
            "avg_inventory": avg_inventory,
            "annual_holding_cost": annual_holding_cost,
            "annual_setup_cost": annual_setup_cost
        })
    return results

# -----------------------------
# FORMULA-BASED JRP POLICY (Lecture Procedure)
# -----------------------------
def find_formula_policy(params: JRPParams) -> Dict[str, Any]:
    items = params.items
    A, r = params.A, params.r

    # Step 1: rank items
    ratios = [(it.a / (it.D * it.v), it) for it in items]
    ratios.sort(key=lambda x: x[0])
    ordered_items = [it for _, it in ratios]

    # Step 2: set m1 = 1
    m_list = [1]
    base_item = ordered_items[0]

    # Step 3: compute other m_j
    for it in ordered_items[1:]:
        m_val = math.sqrt((it.a * base_item.D * base_item.v) / ((A + base_item.a) * (it.D * it.v)))
        m_list.append(max(1, int(round(m_val))))

    # Step 4: compute T*
    numerator = 2 * (A + sum(it.a / m for it, m in zip(ordered_items, m_list)))
    denominator = r * sum(it.D * it.v * m for it, m in zip(ordered_items, m_list))
    if denominator <= 0:
        raise ValueError("Denominator for T* is non-positive; check parameters.")
    T_star = math.sqrt(numerator / denominator)

    # Step 5: compute item metrics
    item_results = compute_item_metrics(ordered_items, T_star, m_list, r)

    # Costs via lecture TRC
    cb = total_cost(A, r, ordered_items, T_star, m_list)

    # Restore original order
    id_to_result = {res["id"]: res for res in item_results}
    ordered_results = [id_to_result[it.id] for it in items]
    ordered_m = [res["m"] for res in ordered_results]

    return {
        "T_star": T_star,
        "m": ordered_m,
        "item_results": ordered_results,
        "total_cost": cb["total"],
        "cost_breakdown": cb,
        "meta": {"method": "formula"}
    }

# -----------------------------
# COMPARISON HELPER
# -----------------------------
def compare_policies(sol1: Dict[str, Any], sol2: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "T_star_diff": (sol1["T_star"] or 0) - (sol2["T_star"] or 0),
        "cost_diff": sol1["total_cost"] - sol2["total_cost"],
        "better": "Instance 1" if sol1["total_cost"] < sol2["total_cost"] else "Instance 2",
        "items_count_diff": len(sol1["item_results"]) - len(sol2["item_results"])
    }

# -----------------------------
# INDEPENDENT EOQ POLICY
# -----------------------------
def find_independent_policy(params: JRPParams) -> Dict[str, Any]:
    items = params.items
    A, r = params.A, params.r

    item_results = []
    total_cost = 0.0
    total_setup = 0.0
    total_holding = 0.0

    for it in items:
        DiVi = it.D * it.v
        Q_i = math.sqrt((2.0 * (A + it.a) * it.D) / (r * it.v))
        cycle_time = Q_i / it.D
        avg_inventory = Q_i / 2.0

        # Costs
        annual_setup_cost = (A + it.a) * (it.D / Q_i)
        annual_holding_cost = avg_inventory * it.v * r
        TC_i = annual_setup_cost + annual_holding_cost

        total_cost += TC_i
        total_setup += annual_setup_cost
        total_holding += annual_holding_cost

        item_results.append({
            "id": it.id,
            "DiVi": DiVi,
            "m": 1,
            "cycle_time": cycle_time,
            "avg_inventory": avg_inventory,
            "annual_holding_cost": annual_holding_cost,
            "annual_setup_cost": annual_setup_cost,
            "Q_i": Q_i,
            "total_cost_item": TC_i
        })

    return {
        "T_star": None,
        "m": [1] * len(items),
        "item_results": item_results,
        "total_cost": total_cost,
        "cost_breakdown": {
            "family_setup": None,
            "item_setup": total_setup,
            "holding": total_holding
        },
        "meta": {"method": "independent_eoq"}
    }

# -----------------------------
# SENSITIVITY ANALYSIS HELPERS (formula policy only)
# -----------------------------
def sensitivity_curve_over_A(params: JRPParams, A_values: List[float]) -> Tuple[List[float], List[float]]:
    x_vals, y_vals = [], []
    for A_val in A_values:
        local_params = JRPParams(A=A_val, r=params.r, items=params.items)
        sol = find_formula_policy(local_params)
        x_vals.append(A_val)
        y_vals.append(sol["total_cost"])
    return x_vals, y_vals

def sensitivity_curve_over_r(params: JRPParams, r_values: List[float]) -> Tuple[List[float], List[float]]:
    x_vals, y_vals = [], []
    for r_val in r_values:
        local_params = JRPParams(A=params.A, r=r_val, items=params.items)
        sol = find_formula_policy(local_params)
        x_vals.append(r_val)
        y_vals.append(sol["total_cost"])
    return x_vals, y_vals

def sensitivity_curve_over_item(params: JRPParams, item_id: str, key: str, values: List[float]) -> Tuple[List[float], List[float]]:
    valid_keys = {"a", "D", "v"}
    if key not in valid_keys:
        raise ValueError(f"key must be one of {valid_keys}")

    x_vals, y_vals = [], []
    for val in values:
        new_items = []
        for it in params.items:
            if it.id == item_id:
                if key == "a":
                    new_items.append(Item(id=it.id, a=val, D=it.D, v=it.v))
                elif key == "D":
                    new_items.append(Item(id=it.id, a=it.a, D=val, v=it.v))
                elif key == "v":
                    new_items.append(Item(id=it.id, a=it.a, D=it.D, v=val))
            else:
                new_items.append(it)
        local_params = JRPParams(A=params.A, r=params.r, items=new_items)
        sol = find_formula_policy(local_params)
        x_vals.append(val)
        y_vals.append(sol["total_cost"])
    return x_vals, y_vals