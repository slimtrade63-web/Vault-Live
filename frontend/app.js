// --- Configuration ---
const API_BASE = "https://vault-live-backend.onrender.com/scan";
const API_ROOT = "https://vault-live-backend.onrender.com";
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

const buttonsDiv    = document.getElementById("buttons");
const resultsTable  = document.getElementById("results").querySelector("tbody");
const reportBtn     = document.getElementById("report-btn");

// --- Create Strategy Buttons ---
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
    const res  = await fetch(`${API_BASE}/${name}`);
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
    document.getElementById("result-count").textContent   = `Results: ${data.results.length}`;
    renderTable(data.results);
  } catch (err) {
    resultsTable.innerHTML = `<tr><td colspan="4">Error fetching data: ${err}</td></tr>`;
  }
}

// --- Render Results Table ---
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

  const now     = new Date();
  const dateStr = now.toISOString().slice(0, 10);
  const timeStr = now.toTimeString().slice(0, 8).replaceAll(":", "-");
  const filename = `${lastScanName.replaceAll(" ", "_")}_${dateStr}_${timeStr}.txt`;

  const metricLabel = lastScanData[0]?.metric_label || "Metric";
  const divider     = "-".repeat(70);
  const header      = `${"Symbol".padEnd(10)} ${"Current Price".padEnd(15)} ${"Trigger Price".padEnd(15)} ${metricLabel}`;
  const rows        = lastScanData.map(d =>
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

  const blob = new Blob([report], { type: "text/plain" });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement("a");
  a.href     = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

reportBtn.addEventListener("click", generateReport);

// --- Load Regime ---
async function loadRegime() {
  try {
    const res  = await fetch(`${API_ROOT}/regime`);
    const data = await res.json();
    if (!data) return;

    const bar = document.getElementById("regime-bar");
    bar.style.borderLeft = `4px solid ${data.color}`;

    document.getElementById("regime-label").textContent       = `📊 ${data.phase}`;
    document.getElementById("regime-label").style.color       = data.color;
    document.getElementById("regime-confidence").textContent  = `Confidence: ${data.confidence}%`;
    document.getElementById("regime-description").textContent = data.description;
    document.getElementById("regime-timestamp").textContent   = `Updated: ${new Date(data.timestamp).toLocaleTimeString()}`;
  } catch (err) {
    document.getElementById("regime-label").textContent = "Regime unavailable";
  }
}

// --- Load Sector Strength ---
async function loadSectors() {
  try {
    const res    = await fetch(`${API_ROOT}/sectors`);
    const sectors = await res.json();
    if (!sectors || !sectors.length) return;

    const chart = document.getElementById("sector-chart");
    chart.innerHTML = "";

    // Find max absolute composite for scaling bars
    const maxVal = Math.max(...sectors.map(s => Math.abs(s.composite)), 1);

    sectors.forEach(s => {
      const isRef     = s.vs_spy === "reference";
      const barClass  = isRef ? "bar-reference" : s.vs_spy === "leading" ? "bar-leading" : s.vs_spy === "lagging" ? "bar-lagging" : "bar-inline";
      const barWidth  = isRef ? 50 : Math.min(Math.abs(s.composite) / maxVal * 100, 100);
      const sign      = s.rel_perf >= 0 ? "+" : "";

      chart.innerHTML += `
        <div class="sector-row">
          <div class="sector-label">
            <span>${s.name}</span>
            <span>${isRef ? "REF" : sign + s.rel_perf + "%"}</span>
          </div>
          <div class="sector-bar-bg">
            <div class="sector-bar-fill ${barClass}" style="width:${barWidth}%"></div>
          </div>
        </div>
      `;
    });

    document.getElementById("sector-timestamp").textContent =
      `Updated: ${new Date().toLocaleTimeString()}`;
  } catch (err) {
    document.getElementById("sector-chart").innerHTML = "<p>Sector data unavailable</p>";
  }
}

// --- Initial Load ---
loadRegime();
loadSectors();