// Change this to your deployed backend later (Render/Fly/Railway)
// For local dev:
const API_BASE = "http://127.0.0.1:5000";
document.getElementById("apiBase").textContent = API_BASE;

const LS_KEY = "batteryguard_runs_v1";

const runForm = document.getElementById("runForm");
const statusEl = document.getElementById("status");

const outputEmpty = document.getElementById("outputEmpty");
const outputArea = document.getElementById("outputArea");
const plotImg = document.getElementById("plotImg");
const jsonPreview = document.getElementById("jsonPreview");
const downloadJsonBtn = document.getElementById("downloadJsonBtn");

const historyEmpty = document.getElementById("historyEmpty");
const historyList = document.getElementById("historyList");

const clearBtn = document.getElementById("clearBtn");

let lastResult = null;

function loadRuns() {
  try {
    return JSON.parse(localStorage.getItem(LS_KEY) || "[]");
  } catch {
    return [];
  }
}

function saveRuns(runs) {
  localStorage.setItem(LS_KEY, JSON.stringify(runs));
}

function renderHistory() {
  const runs = loadRuns();

  historyList.innerHTML = "";
  if (runs.length === 0) {
    historyEmpty.classList.remove("hidden");
    return;
  }
  historyEmpty.classList.add("hidden");

  runs.slice().reverse().forEach((r) => {
    const li = document.createElement("li");

    const left = document.createElement("div");
    left.innerHTML = `
      <strong>${r.meta.model}</strong>
      <div><small>${new Date(r.saved_at).toLocaleString()}</small></div>
      <div><small>C-rate: ${r.meta.inputs.c_rate}, hours: ${r.meta.inputs.t_hours}, SOC: ${r.meta.inputs.init_soc}</small></div>
    `;

    const right = document.createElement("div");
    const btn = document.createElement("button");
    btn.className = "secondary";
    btn.textContent = "Load";
    btn.onclick = () => showResult(r);
    right.appendChild(btn);

    li.appendChild(left);
    li.appendChild(right);

    historyList.appendChild(li);
  });
}

function showResult(payload) {
  lastResult = payload;
  outputEmpty.classList.add("hidden");
  outputArea.classList.remove("hidden");

  // plot is optional when loading from history
  if (payload.plot_png_base64) {
    plotImg.src = payload.plot_png_base64;
  } else {
    plotImg.removeAttribute("src");
  }

  jsonPreview.textContent = JSON.stringify(payload.result, null, 2);
}

function downloadJson(obj, filename = "pybamm_result.json") {
  const blob = new Blob([JSON.stringify(obj, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);

  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();

  URL.revokeObjectURL(url);
}

runForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  statusEl.textContent = "Running simulation...";

  const payload = {
    model: document.getElementById("model").value,
    c_rate: Number(document.getElementById("c_rate").value),
    t_hours: Number(document.getElementById("t_hours").value),
    init_soc: Number(document.getElementById("init_soc").value),
  };

  try {
    const res = await fetch(`${API_BASE}/api/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.error || "Unknown error");
    }

    // Save a compact run record
    const runRecord = {
      saved_at: new Date().toISOString(),
      result: data.result,
      meta: data.result.meta,
      plot_png_base64: data.plot_png_base64, // keep it for reload convenience
    };

    // localStorage (Option B)
    const runs = loadRuns();
    runs.push(runRecord);
    saveRuns(runs);

    showResult({ result: data.result, plot_png_base64: data.plot_png_base64 });
    renderHistory();

    statusEl.textContent = "Done ✅ Saved to history.";
  } catch (err) {
    statusEl.textContent = `Failed ❌ ${err.message}. Is the backend running?`;
  }
});

downloadJsonBtn.addEventListener("click", () => {
  if (!lastResult) return;
  downloadJson(lastResult.result);
});

clearBtn.addEventListener("click", () => {
  localStorage.removeItem(LS_KEY);
  renderHistory();
  statusEl.textContent = "History cleared.";
});

renderHistory();
