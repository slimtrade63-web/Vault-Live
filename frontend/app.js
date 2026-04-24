// --- Configuration ---
// --- Configuration ---
const API_BASE = "https://vault-live.onrender.com/scan";

// --- State ---
let lastScanData = null;
let lastScanName = null;

// --- Strategy List ---
const strategies = [
  "momentum_buy",
  "long_term_momentum",
  "trapped_longs",
  "trapped_shorts",
  "bull_coil",
  "bear_coil",
  "bull_reversion",
  "bear_reversion"
];

const buttonsDiv = document.getElementById("buttons");
const resultsTable = document.getElementById("results").querySelector("tbody");
const reportBtn = document.getElementById("report-btn");

// --- Create Buttons ---
strategies.forEach(name => {
  const btn = document.createElement("button");
  btn.textContent = name.replaceAll("_", " ");
  btn.onclick = () => runScan(name);
  buttonsDiv.appendChild(btn);
});

// --- Run Strategy ---
async function runScan(name) {
  resultsTable.innerHTML = `<tr><td colspan="4">⏳ Scanning ${name}...</td></tr>`;
  reportBtn.disabled = true;
  try {
    const res = await fetch(`${API_BASE}/${name}`);
    const data = await res.json();

    if (!data.results || data.results.length === 0) {
      resultsTable.innerHTML = `<tr><td colspan="4">No results found for ${name}</td></tr>`;
      document.getElementById("result-count").textContent = "";
      document.getElementById("strategy-label").textContent = name.replaceAll("_", " ");
      lastScanData = null;
      lastScanName = null;
      return;
    }

    lastScanData = data.results;
    lastScanName = data.strategy;
    reportBtn.disabled = false;

    document.getElementById("strategy-label").textContent = data.strategy;
    document.getElementById("result-count").textContent = `Results: ${data.results.length}`;
    renderTable(data.results);
  } catch (err) {
    resultsTable.innerHTML = `<tr><td colspan="4">Error fetching data: ${err}</td></tr>`;
  }
}

// --- Render Table ---
function renderTable(rows) {
  if (rows.length === 0) return;
  document.querySelector("#results thead tr th:last-child").textContent = rows[0].metric_label;
  resultsTable.innerHTML = rows.map(d => `
    <tr>
      <td>${d.symbol}</td>
      <td>${d.current_price}</td>
      <td>${d.trigger_price}</td>
      <td>${d.metric}%</td>
    </tr>
  `).join("");
}

// --- Generate Report ---
function generateReport() {
  if (!lastScanData || !lastScanName) return;

  const now = new Date();
  const dateStr = now.toISOString().slice(0, 10);
  const timeStr = now.toTimeString().slice(0, 8).replaceAll(":", "-");
  const filename = `${lastScanName.replaceAll(" ", "_")}_${dateStr}_${timeStr}.txt`;

  const metricLabel = lastScanData[0]?.metric_label || "Metric";

  // Build header
  const col1 = "Symbol";
  const col2 = "Current Price";
  const col3 = "Trigger Price";
  const col4 = metricLabel;

  const divider = "-".repeat(70);
  const header = `${col1.padEnd(10)} ${col2.padEnd(15)} ${col3.padEnd(15)} ${col4}`;

  const rows = lastScanData.map(d =>
    `${d.symbol.padEnd(10)} ${String(d.current_price).padEnd(15)} ${String(d.trigger_price).padEnd(15)} ${d.metric}%`
  ).join("\n");

  const report = [
    `VAULT V80 INSTITUTIONAL SCANNER`,
    `Strategy: ${lastScanName}`,
    `Generated: ${now.toLocaleString()}`,
    `Results: ${lastScanData.length}`,
    ``,
    divider,
    header,
    divider,
    rows,
    divider,
  ].join("\n");

  // Trigger download
  const blob = new Blob([report], { type: "text/plain" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

reportBtn.addEventListener("click", generateReport);