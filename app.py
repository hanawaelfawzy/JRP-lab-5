import streamlit as st
import json
import numpy as np

from io_utils.input_loader import load_and_validate_from_json
from io_utils.output_exporter import (
    solution_to_json,
    solution_markdown_report,
    solution_pdf_bytes,
    plot_cost_breakdown,
    plot_cost_pie,
    plot_joint_vs_independent,
    plot_inventory_cycles,
    plot_comparison_total_cost,
    plot_comparison_item_costs,
    plot_comparison_cycles,
    plot_sensitivity_curve,
    plot_sensitivity_item_m
)
from models.jrp_solver import (
    find_formula_policy,
    find_independent_policy,
    sensitivity_curve_over_A,
    sensitivity_curve_over_r
)

st.set_page_config(page_title="Joint Replenishment Planning", layout="wide")
st.title("Joint Replenishment Planning (Deterministic)")

def compare_policies(sol1: dict, sol2: dict) -> dict:
    """Compare two solutions and return differences in T* and cost."""
    t_star_diff = sol1["T_star"] - sol2["T_star"]
    cost_diff = sol1["total_cost"] - sol2["total_cost"]

    better = "Instance 1" if sol1["total_cost"] < sol2["total_cost"] else "Instance 2"

    return {
        "T_star_diff": t_star_diff,
        "cost_diff": cost_diff,
        "better": better
    }

# -----------------------------
# Sidebar controls
# -----------------------------
mode = st.sidebar.radio("Mode", ["Single Instance", "Comparison Mode", "Sensitivity Analysis"])
st.sidebar.header("Upload or select example")

# Demo examples
example_small = {
    "instance_name": "Small_Example",
    "A": 40.0,
    "r": 0.24,
    "items": [
        {"id": "1L", "a": 15.0, "D": 500.0, "v": 2.0},
        {"id": "5L", "a": 15.0, "D": 300.0, "v": 2.5},
        {"id": "10L","a": 15.0, "D": 200.0, "v": 3.0}
    ]
}
example_large = {
    "instance_name": "Large_Example",
    "A": 120.0,
    "r": 0.18,
    "items": [
        {"id": f"Item{i}", "a": 10.0 + (i % 3) * 5, "D": 100.0 + 20 * i, "v": 2.0 + 0.2 * (i % 5)}
        for i in range(1, 12)
    ]
}

example_choice = st.sidebar.selectbox("Choose demo instance", ["None", "Small_Example", "Large_Example"])
st.sidebar.markdown("---")

# -----------------------------
# SINGLE INSTANCE MODE
# -----------------------------
if mode == "Single Instance":
    uploaded = st.sidebar.file_uploader("Upload JSON input file", type=["json"], key="single_instance_upload")
    instance_name = None
    raw_data = None
    params = None
    errors = []

    if uploaded is not None:
        file_bytes = uploaded.read()
        params, raw_data, errors = load_and_validate_from_json(file_bytes)
        instance_name = raw_data.get("instance_name", "Instance")
    elif example_choice == "Small_Example":
        raw_data = example_small
        params, raw_data, errors = load_and_validate_from_json(json.dumps(raw_data).encode("utf-8"))
        instance_name = raw_data["instance_name"]
    elif example_choice == "Large_Example":
        raw_data = example_large
        params, raw_data, errors = load_and_validate_from_json(json.dumps(raw_data).encode("utf-8"))
        instance_name = raw_data["instance_name"]

    st.markdown("## Input summary")

    if raw_data is None:
        st.info("Upload a JSON file or select a demo instance from the sidebar.")
    else:
        if errors:
            st.error("Input validation failed:")
            for e in errors:
                st.markdown(f"- {e}")
        else:
            col1, col2 = st.columns([1, 2])
            with col1:
                st.markdown(f"**Instance name:** {raw_data.get('instance_name', 'N/A')}")
                st.markdown(f"**A (major setup):** {raw_data['A']}")
                st.markdown(f"**r (carrying charge):** {raw_data['r']}")
                st.markdown(f"**Items (n):** {len(raw_data['items'])}")
            with col2:
                st.dataframe(
                    {
                        "id": [it["id"] for it in raw_data["items"]],
                        "a": [it["a"] for it in raw_data["items"]],
                        "D": [it["D"] for it in raw_data["items"]],
                        "v": [it["v"] for it in raw_data["items"]],
                    },
                    use_container_width=True
                )

            st.markdown("---")
            st.markdown("## Solve")

            if st.button("Run optimization"):
                # Compute both solutions
                sol_joint = find_formula_policy(params)
                sol_ind = find_independent_policy(params)

                st.success("Optimization complete.")
                c1, c2 = st.columns(2)
                with c1:
                    st.metric("T* (basic cycle time)", f"{sol_joint['T_star']:.6f}")
                with c2:
                    st.metric("Total cost (per unit time)", f"{sol_joint['total_cost']:.6f}")

                st.markdown("### Cost breakdown")
                st.table({
                    "Component": ["Family setup", "Item setup", "Holding"],
                    "Cost": [
                        sol_joint["cost_breakdown"]["family_setup"],
                        sol_joint["cost_breakdown"]["item_setup"],
                        sol_joint["cost_breakdown"]["holding"]
                    ]
                })

                st.markdown("### Per-item results")
                st.dataframe(
                    {k: [it[k] for it in sol_joint["item_results"]] for k in sol_joint["item_results"][0]},
                    use_container_width=True
                )

                st.markdown("---")
                st.markdown("## Visualizations")
                # Order: cycles -> joint vs independent -> breakdown -> pie
                st.plotly_chart(plot_inventory_cycles(sol_joint, raw_data), use_container_width=True)
                st.plotly_chart(plot_joint_vs_independent(sol_joint, sol_ind), use_container_width=True)
                st.plotly_chart(plot_cost_breakdown(sol_joint), use_container_width=True)
                st.plotly_chart(plot_cost_pie(sol_joint), use_container_width=True)

                # Export buttons
                st.download_button(
                    "Download JSON",
                    solution_to_json(instance_name, "formula", raw_data, sol_joint),
                    file_name=f"{instance_name}_solution.json"
                )
                st.download_button(
                    "Download Markdown",
                    solution_markdown_report(instance_name, raw_data, sol_joint),
                    file_name=f"{instance_name}_report.md"
                )
                st.download_button(
                    "Download PDF",
                    solution_pdf_bytes(instance_name, raw_data, sol_joint, sol_ind),
                    file_name=f"{instance_name}_report.pdf"
                )

# -----------------------------
# COMPARISON MODE
# -----------------------------
elif mode == "Comparison Mode":
    st.markdown("## Comparison Mode")

    # Two separate uploaders
    file1 = st.sidebar.file_uploader("Upload first JSON file", type=["json"], key="file1")
    file2 = st.sidebar.file_uploader("Upload second JSON file", type=["json"], key="file2")

    if file1 and file2 and st.button("Run comparison"):
        file_bytes1 = file1.read()
        file_bytes2 = file2.read()

        params1, raw1, errors1 = load_and_validate_from_json(file_bytes1)
        params2, raw2, errors2 = load_and_validate_from_json(file_bytes2)

        if errors1 or errors2:
            st.error("Validation failed.")
            if errors1:
                st.markdown("**Instance 1 errors:**")
                for e in errors1:
                    st.markdown(f"- {e}")
            if errors2:
                st.markdown("**Instance 2 errors:**")
                for e in errors2:
                    st.markdown(f"- {e}")
        else:
            sol1_joint = find_formula_policy(params1)
            sol2_joint = find_formula_policy(params2)

            st.success("Comparison complete.")

            # Side-by-side metrics
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("### Instance 1")
                st.metric("T*", f"{sol1_joint['T_star']:.6f}")
                st.metric("Total cost", f"{sol1_joint['total_cost']:.6f}")
            with c2:
                st.markdown("### Instance 2")
                st.metric("T*", f"{sol2_joint['T_star']:.6f}")
                st.metric("Total cost", f"{sol2_joint['total_cost']:.6f}")

            # Graphs
            st.markdown("### Total Cost Comparison")
            st.plotly_chart(
                plot_comparison_total_cost(
                    sol1_joint, sol2_joint,
                    raw1.get("instance_name","Instance 1"),
                    raw2.get("instance_name","Instance 2")
                ),
                use_container_width=True
            )

            st.markdown("### Item Cost Comparison")
            fig_hold, fig_setup = plot_comparison_item_costs(
                sol1_joint, sol2_joint,
                raw1.get("instance_name","Instance 1"),
                raw2.get("instance_name","Instance 2")
            )
            st.plotly_chart(fig_hold, use_container_width=True)
            st.plotly_chart(fig_setup, use_container_width=True)


            # Textual summary
            diff = compare_policies(sol1_joint, sol2_joint)
            st.markdown("### Summary")
            st.write(f"Difference in T*: {diff['T_star_diff']:.6f}")
            st.write(f"Difference in total cost: {diff['cost_diff']:.6f}")
            st.write(f"Better policy: {diff['better']}")

            # Export PDF
            st.download_button(
                "Download Comparison PDF",
                solution_pdf_bytes(
                    f"{raw1.get('instance_name','Instance 1')} vs {raw2.get('instance_name','Instance 2')}",
                    raw1, sol1_joint, sol2_joint
                ),
                file_name="comparison_report.pdf"
            )
    else:
        st.info("Upload two JSON files and click 'Run comparison'.")
# -----------------------------
# SENSITIVITY ANALYSIS
# -----------------------------
elif mode == "Sensitivity Analysis":
    st.markdown("## Sensitivity Analysis")
    uploaded_sa = st.sidebar.file_uploader("Upload JSON input file", type=["json"], key="sensitivity_upload")

    if uploaded_sa:
        file_bytes = uploaded_sa.read()
        params, raw_data, errors = load_and_validate_from_json(file_bytes)

        if errors:
            st.error("Validation failed:")
            for e in errors:
                st.write("-", e)
        else:
            st.success("Instance loaded.")
            st.markdown("### Choose parameter to vary")
            choice = st.radio("Parameter", ["A (major setup)", "r (carrying charge)"])

            if choice == "A (major setup)":
                # sliders for A
                A_min = st.slider("Minimum A", 10.0, 200.0, 20.0)
                A_max = st.slider("Maximum A", 10.0, 200.0, 100.0)
                steps = st.slider("Number of steps", 5, 50, 20)
                A_values = np.linspace(A_min, A_max, steps)
                x_vals, y_vals = sensitivity_curve_over_A(params, A_values)
                st.plotly_chart(plot_sensitivity_curve(x_vals, y_vals, "A", "Sensitivity over A"), use_container_width=True)

            elif choice == "r (carrying charge)":
                r_min = st.slider("Minimum r", 0.01, 1.0, 0.05)
                r_max = st.slider("Maximum r", 0.01, 1.0, 0.5)
                steps = st.slider("Number of steps", 5, 50, 20)
                r_values = np.linspace(r_min, r_max, steps)
                x_vals, y_vals = sensitivity_curve_over_r(params, r_values)
                st.plotly_chart(plot_sensitivity_curve(x_vals, y_vals, "r", "Sensitivity over r"), use_container_width=True)
    else:
        st.info("Upload a JSON file to run sensitivity analysis.")