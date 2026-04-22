// --- Configuration ---
 const API= "http://vault-live.onrender.com/scan";

// --- Strategy List ---
const strategies = [
  "momentum_buy",
  "long_term_momentum",
  "trapped_longs",
  "trapped_shorts",
  "bull_reversion",
  "bear_reversion",
  "bull_coil",
  "bear_coil"
];

const buttonsDiv = document.getElementById("buttons");
const resultsTable = document.getElementById("results").querySelector("tbody");

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
  try {
    const res = await fetch(`${API_BASE}/${name}`);
    const data = await res.json();

    if (!data.results || data.results.length === 0) {
      resultsTable.innerHTML = `<tr><td colspan="4">No results found for ${name}</td></tr>`;
      document.getElementById("result-count").textContent = "";
      return;
    }

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
  
  // Update the column header dynamically
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
