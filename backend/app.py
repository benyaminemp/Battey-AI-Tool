from flask import Flask, request, jsonify
from flask_cors import CORS
import io
import base64
import json
import numpy as np
import matplotlib.pyplot as plt

import pybamm

app = Flask(__name__)
CORS(app)  # allow frontend to call backend during dev


def run_pybamm_simulation(c_rate: float, t_hours: float, init_soc: float, model_name: str):
    """
    Run a simple PyBaMM simulation and return (time_s, voltage_v, current_a, metadata)
    """
    # Choose a basic model
    if model_name == "SPM":
        model = pybamm.lithium_ion.SPM()
    else:
        # Thevenin-equivalent style model (faster, simple)
        model = pybamm.lithium_ion.Thevenin()

    # Parameter set (works well out-of-the-box)
    param = pybamm.ParameterValues("Chen2020")

    # Experiment: constant current discharge at C-rate
    # NOTE: In PyBaMM, many experiments expect strings like "1C discharge for 1 hour"
    experiment = pybamm.Experiment(
        [f"{c_rate}C discharge for {t_hours} hours"],
        # you can add: temperature, rest steps, etc later
    )

    sim = pybamm.Simulation(model, parameter_values=param, experiment=experiment)

    # Set initial SOC (0..1)
    sim.solve(initial_soc=init_soc)

    sol = sim.solution

    t = sol["Time [s]"].entries
    V = sol["Terminal voltage [V]"].entries

    # Current might exist as "Current [A]" depending on model; safe fallback:
    # For many experiments, current is controlled but can be extracted differently.
    # We'll compute an approximate current from C-rate and nominal capacity.
    # Chen2020 nominal capacity ~ 5 Ah (commonly)
    nominal_capacity_ah = 5.0
    I = np.ones_like(t) * (c_rate * nominal_capacity_ah)  # A (approx)
    I = -I  # discharge negative (convention)

    meta = {
        "model": model_name,
        "parameter_set": "Chen2020",
        "inputs": {
            "c_rate": c_rate,
            "t_hours": t_hours,
            "init_soc": init_soc,
        },
        "outputs": {
            "n_points": int(len(t)),
            "v_min": float(np.min(V)),
            "v_max": float(np.max(V)),
        },
    }

    return t, V, I, meta


def make_voltage_plot_png_base64(t_s, V):
    """
    Create a simple voltage vs time plot and return base64 PNG.
    """
    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.plot(t_s / 60.0, V)
    ax.set_xlabel("Time [min]")
    ax.set_ylabel("Terminal Voltage [V]")
    ax.set_title("PyBaMM Simulation: Voltage vs Time")
    ax.grid(True)

    buf = io.BytesIO()
    plt.tight_layout()
    fig.savefig(buf, format="png", dpi=160)
    plt.close(fig)
    buf.seek(0)

    b64 = base64.b64encode(buf.read()).decode("utf-8")
    return f"data:image/png;base64,{b64}"


@app.route("/api/run", methods=["POST"])
def api_run():
    data = request.get_json(force=True)

    # Simple validation + defaults
    try:
        c_rate = float(data.get("c_rate", 1.0))
        t_hours = float(data.get("t_hours", 1.0))
        init_soc = float(data.get("init_soc", 1.0))
        model_name = str(data.get("model", "SPM")).upper()

        if c_rate <= 0:
            return jsonify({"error": "c_rate must be > 0"}), 400
        if t_hours <= 0:
            return jsonify({"error": "t_hours must be > 0"}), 400
        if not (0.0 <= init_soc <= 1.0):
            return jsonify({"error": "init_soc must be in [0, 1]"}), 400
        if model_name not in ["SPM", "THEVENIN"]:
            return jsonify({"error": "model must be SPM or THEVENIN"}), 400

        # normalize
        model_name = "SPM" if model_name == "SPM" else "Thevenin"

    except Exception as e:
        return jsonify({"error": f"Invalid input: {str(e)}"}), 400

    try:
        t, V, I, meta = run_pybamm_simulation(c_rate, t_hours, init_soc, model_name)
        plot_b64 = make_voltage_plot_png_base64(t, V)

        # Build a JSON-friendly result
        result = {
            "meta": meta,
            "series": {
                "time_s": t.tolist(),
                "voltage_v": V.tolist(),
                "current_a": I.tolist(),
            },
        }

        return jsonify({
            "result": result,
            "plot_png_base64": plot_b64
        })

    except Exception as e:
        return jsonify({"error": f"Simulation failed: {str(e)}"}), 500


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    # Run: python app.py
    app.run(host="127.0.0.1", port=5000, debug=True)
