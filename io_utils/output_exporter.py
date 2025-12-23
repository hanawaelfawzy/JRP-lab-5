import json
from datetime import datetime
from typing import Dict, Any
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import io   # <-- add this line
import tempfile
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether

# -----------------------------
# JSON Export
# -----------------------------
def solution_to_json(instance_name: str, model_type: str, raw_params: Dict[str, Any], sol: Dict[str, Any]) -> str:
    payload = {
        "problem_metadata": {
            "instance_name": instance_name,
            "model_type": model_type,
            "timestamp": datetime.now().isoformat()
        },
        "parameters": {
            "A": float(raw_params["A"]),
            "r": float(raw_params["r"]),
            "items": raw_params["items"]
        },
        "solution": {
            "T_star": sol["T_star"],
            "items": sol["item_results"],
            "total_annual_cost": sol["total_cost"],
            "cost_breakdown": sol["cost_breakdown"],
            "meta": sol.get("meta", {})
        }
    }
    return json.dumps(payload, indent=2)

# -----------------------------
# Markdown Report
# -----------------------------
def solution_markdown_report(instance_name: str, raw_params: Dict[str, Any], sol: Dict[str, Any]) -> str:
    lines = []
    lines.append(f"# Joint Replenishment Report — {instance_name}")
    lines.append("")
    lines.append(f"Generated: {datetime.now().isoformat()}")
    lines.append("")
    lines.append("## Input parameters")
    lines.append("")
    lines.append(f"- **A (major setup):** {raw_params['A']}")
    lines.append(f"- **r (carrying charge):** {raw_params['r']}")
    lines.append(f"- **Items:**")
    for it in raw_params["items"]:
        lines.append(f"  - **ID:** {it['id']}, **a:** {it['a']}, **D:** {it['D']}, **v:** {it['v']}")
    lines.append("")
    lines.append("## Solution summary")
    lines.append("")
    lines.append(f"- **T***: {sol['T_star']:.6f}")
    lines.append(f"- **Total cost (per unit time):** {sol['total_cost']:.6f}")
    lines.append(f"- **Family setup cost:** {sol['cost_breakdown']['family_setup']:.6f}")
    lines.append(f"- **Item setup cost:** {sol['cost_breakdown']['item_setup']:.6f}")
    lines.append(f"- **Holding cost:** {sol['cost_breakdown']['holding']:.6f}")
    lines.append("")
    lines.append("## Per-item results")
    lines.append("")
    lines.append("| Item | m | Cycle time | Avg inventory | Holding cost | Setup cost |")
    lines.append("|------|---|------------:|--------------:|-------------:|-----------:|")
    for it in sol["item_results"]:
        lines.append(
            f"| {it['id']} | {it['m']} | {it['cycle_time']:.6f} | {it['avg_inventory']:.6f} | "
            f"{it['annual_holding_cost']:.6f} | {it['annual_setup_cost']:.6f} |"
        )
    return "\n".join(lines)

# -----------------------------
# Visualization Functions
# -----------------------------
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

def plot_cost_breakdown(sol: Dict[str, Any]):
    df = pd.DataFrame(sol["item_results"])
    fig = px.bar(
        df,
        x="id",
        y=["annual_holding_cost", "annual_setup_cost"],
        title="Setup & Holding Cost Breakdown per Item",
        barmode="stack"
    )
    return fig

def plot_cost_pie(sol: Dict[str, Any]):
    breakdown = sol["cost_breakdown"]
    fig = go.Figure(data=[go.Pie(
        labels=["Holding", "Item setup", "Family setup"],
        values=[breakdown["holding"], breakdown["item_setup"], breakdown["family_setup"]],
        hole=0.4
    )])
    fig.update_layout(title="Cost Component Breakdown")
    return fig

def plot_joint_vs_independent(sol_joint: Dict[str, Any], sol_ind: Dict[str, Any]):
    fig = go.Figure()
    fig.add_trace(go.Bar(x=["Total Cost"], y=[sol_joint["total_cost"]], name="Joint Order"))
    fig.add_trace(go.Bar(x=["Total Cost"], y=[sol_ind["total_cost"]], name="Independent Orders"))
    fig.update_layout(title="Joint vs Independent Ordering Costs", barmode="group")
    return fig

def plot_inventory_cycles(sol: Dict[str, Any], raw_params: Dict[str, Any], horizon: float = None):
    """
    Generate triangular inventory cycle graph with linear depletion and instant replenishment.
    Uses original demand rate D from raw_params.
    """
    import plotly.graph_objects as go

    items = sol["item_results"]
    T_star = sol["T_star"] or 1.0
    max_m = max(it["m"] for it in items) if items else 1
    horizon = horizon or (max_m * T_star * 3)

    # Build lookup for D from raw_params
    demand_lookup = {it["id"]: it["D"] for it in raw_params["items"]}

    fig = go.Figure()
    color_seq = ["#FFD700", "#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#8c564b"]
    item_order = [it["id"] for it in items]

    for idx, it in enumerate(sorted(items, key=lambda x: item_order.index(x["id"]) if x["id"] in item_order else 999)):
        m = it["m"]
        cycle = m * T_star
        D = demand_lookup.get(it["id"], 0)
        Q = D * cycle
        t = 0.0
        x_vals, y_vals = [], []

        while t <= horizon:
            x_vals += [t, t + cycle]
            y_vals += [Q, 0]
            t += cycle

        fig.add_trace(go.Scatter(
            x=x_vals, y=y_vals, mode="lines", name=it["id"],
            line=dict(shape="linear", width=2, color=color_seq[idx % len(color_seq)])
        ))

    fig.update_layout(
        title="Deterministic Demand Pattern: Inventory Cycles",
        xaxis_title="Time",
        yaxis_title="Inventory Level",
        template="plotly",
        legend_title_text=""
    )
    return fig

# -----------------------------
# Sensitivity Analysis Plots
# -----------------------------
def plot_sensitivity_curve(x_vals, y_vals, param_name: str, title: str):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x_vals, y=y_vals, mode="lines+markers", name=param_name))
    fig.update_layout(title=title, xaxis_title=param_name, yaxis_title="Total Cost", template="plotly")
    return fig

def plot_sensitivity_item_m(sol: Dict[str, Any]):
    df = pd.DataFrame(sol["item_results"])
    fig = px.bar(df, x="id", y="m", title="Item Multipliers (m) under Sensitivity Analysis",
                 labels={"m": "Multiplier"})
    return fig

# -----------------------------
# PDF Export with Colorful Tables + Charts
# -----------------------------
import io
import tempfile
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether

def solution_pdf_bytes(instance_name, raw_params, sol, sol_ind=None):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []

    # Title
    elements.append(Paragraph(f"Joint Replenishment Report — {instance_name}", styles['Title']))
    elements.append(Spacer(1, 12))

    # Input parameters
    elements.append(Paragraph("Input Parameters", styles['Heading2']))
    data_input = [["A (major setup)", raw_params["A"]],
                  ["r (carrying charge)", raw_params["r"]],
                  ["Number of items", len(raw_params["items"])]]
    table_input = Table(data_input, hAlign="LEFT")
    table_input.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#4CAF50")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black)
    ]))
    elements.append(table_input)
    elements.append(Spacer(1, 12))

    # Items table
    elements.append(Paragraph("Items", styles['Heading2']))
    data_items = [["ID", "a", "D", "v"]] + [[it["id"], it["a"], it["D"], it["v"]] for it in raw_params["items"]]
    table_items = Table(data_items, hAlign="LEFT")
    table_items.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#2196F3")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black)
    ]))
    elements.append(table_items)
    elements.append(Spacer(1, 12))

    # Solution summary
    elements.append(Paragraph("Solution Summary", styles['Heading2']))
    data_summary = [["T*", f"{sol['T_star']:.6f}"],
                    ["Total cost", f"{sol['total_cost']:.6f}"],
                    ["Family setup cost", f"{sol['cost_breakdown']['family_setup']:.6f}"],
                    ["Item setup cost", f"{sol['cost_breakdown']['item_setup']:.6f}"],
                    ["Holding cost", f"{sol['cost_breakdown']['holding']:.6f}"]]
    table_summary = Table(data_summary, hAlign="LEFT")
    table_summary.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#FF9800")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black)
    ]))
    elements.append(table_summary)
    elements.append(Spacer(1, 12))

    # Per-item results
    elements.append(Paragraph("Per-Item Results", styles['Heading2']))
    data_results = [["Item", "m", "Cycle Time", "Avg Inventory", "Holding Cost", "Setup Cost"]]
    for it in sol["item_results"]:
        data_results.append([
            it["id"], it["m"], f"{it['cycle_time']:.3f}",
            f"{it['avg_inventory']:.2f}", f"{it['annual_holding_cost']:.2f}",
            f"{it['annual_setup_cost']:.2f}"
        ])
    table_results = Table(data_results, hAlign="LEFT")
    table_results.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#9C27B0")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black)
    ]))
    elements.append(table_results)
    elements.append(Spacer(1, 20))

    # === Visualizations ===
    viz_section = [Paragraph("Visualizations", styles['Heading2'])]

    item_order = [it["id"] for it in raw_params["items"]]

    # 1) Inventory cycles (reuse corrected function)
    fig_cycles = plot_inventory_cycles(sol, raw_params)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmpfile:
        fig_cycles.write_image(tmpfile.name, scale=2)
        viz_section.append(Image(tmpfile.name, width=400, height=300))

    # 2) Joint vs Independent ordering costs
    if sol_ind is not None:
        fig_jrp = go.Figure()
        fig_jrp.add_trace(go.Bar(x=["Total Cost"], y=[sol["total_cost"]],
                                 name="Joint Order", marker_color="#1f77b4"))
        fig_jrp.add_trace(go.Bar(x=["Total Cost"], y=[sol_ind["total_cost"]],
                                 name="Independent Orders", marker_color="#ff7f0e"))
        fig_jrp.update_layout(template="plotly", title="Joint vs Independent Ordering Costs",
                              barmode="group", legend_title_text="")
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmpfile:
            fig_jrp.write_image(tmpfile.name, scale=2)
            viz_section.append(Image(tmpfile.name, width=400, height=300))

    # 3) Setup & Holding cost breakdown per item
    df_items = pd.DataFrame(sol["item_results"])
    df_items["id"] = pd.Categorical(df_items["id"], categories=item_order, ordered=True)
    fig_costs = px.bar(df_items.sort_values("id"), x="id",
                       y=["annual_holding_cost", "annual_setup_cost"],
                       title="Setup & Holding Cost Breakdown per Item",
                       barmode="stack",
                       color_discrete_map={"annual_holding_cost": "#1f77b4", "annual_setup_cost": "#ff7f0e"})
    fig_costs.update_layout(template="plotly", legend_title_text="")
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmpfile:
        fig_costs.write_image(tmpfile.name, scale=2)
        viz_section.append(Image(tmpfile.name, width=400, height=300))

    # 4) Cost component breakdown (pie)
    breakdown = sol["cost_breakdown"]
    labels = ["Holding", "Item setup", "Family setup"]
    values = [breakdown["holding"], breakdown["item_setup"], breakdown["family_setup"]]
    fig_pie = go.Figure(data=[go.Pie(labels=labels, values=values, hole=0.4)])
    fig_pie.update_traces(marker=dict(colors=["#2ca02c", "#ff7f0e", "#1f77b4"]))
    fig_pie.update_layout(template="plotly", title="Cost Component Breakdown", legend_title_text="")
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmpfile:
        fig_pie.write_image(tmpfile.name, scale=2)
        viz_section.append(Image(tmpfile.name, width=400, height=300))

    # Keep all visuals together
    elements.append(KeepTogether(viz_section))

    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer.read()

# Comparison plots
def plot_comparison_total_cost(sol1, sol2, name1="Instance 1", name2="Instance 2"):
    fig = go.Figure()
    fig.add_trace(go.Bar(x=[name1], y=[sol1["total_cost"]], name=name1))
    fig.add_trace(go.Bar(x=[name2], y=[sol2["total_cost"]], name=name2))
    fig.update_layout(title="Total Cost Comparison", barmode="group")
    return fig

def plot_comparison_item_costs(sol1, sol2, name1="Instance 1", name2="Instance 2"):
    df1 = pd.DataFrame(sol1["item_results"]); df1["instance"] = name1
    df2 = pd.DataFrame(sol2["item_results"]); df2["instance"] = name2
    df = pd.concat([df1, df2])
    fig_hold = px.bar(df, x="id", y="annual_holding_cost", color="instance",
                      barmode="group", title="Holding Cost Comparison")
    fig_setup = px.bar(df, x="id", y="annual_setup_cost", color="instance",
                       barmode="group", title="Setup Cost Comparison")
    return fig_hold, fig_setup

def plot_comparison_cycles(sol1, sol2, name1="Instance 1", name2="Instance 2"):
    fig = go.Figure()
    for it in sol1["item_results"]:
        fig.add_trace(go.Scatter(
            x=[it["id"]],
            y=[it["cycle_time"]],
            mode="markers",
            name=f"{name1}-{it['id']}"
        ))
    for it in sol2["item_results"]:
        fig.add_trace(go.Scatter(
            x=[it["id"]],
            y=[it["cycle_time"]],
            mode="markers",
            name=f"{name2}-{it['id']}"
        ))
    fig.update_layout(
        title="Cycle Time Comparison",
        xaxis_title="Item",
        yaxis_title="Cycle Time"
    )
    return fig