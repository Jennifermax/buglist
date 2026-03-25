const state = {
  config: {},
  cases: [],
  runs: [],
  bugs: []
};

const $ = (id) => document.getElementById(id);

const configFields = [
  "projectName",
  "zentaoBaseUrl",
  "submitMode",
  "zentaoProductId",
  "zentaoProjectId",
  "zentaoModuleId",
  "zentaoOpenedBuild",
  "zentaoToken",
  "zentaoAccount",
  "zentaoPassword",
  "zentaoCliPath",
  "automationCommand"
];

function escapeHtml(text) {
  return String(text || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function request(url, options = {}) {
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json"
    },
    ...options
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "Request failed");
  }
  return data;
}

function renderMetrics() {
  const latestRun = state.runs[0];
  const latestSummary = latestRun ? latestRun.summary : { passed: 0, failed: 0 };
  $("heroMetrics").innerHTML = `
    <div class="metric">
      <strong>${state.cases.length}</strong>
      <span>Test Cases</span>
    </div>
    <div class="metric">
      <strong>${state.runs.length}</strong>
      <span>Runs</span>
    </div>
    <div class="metric">
      <strong>${state.bugs.length}</strong>
      <span>Bug Drafts</span>
    </div>
    <div class="metric">
      <strong>${latestSummary.failed || 0}</strong>
      <span>Latest Failed</span>
    </div>
  `;
}

function fillConfig() {
  configFields.forEach((key) => {
    if ($(key)) {
      $(key).value = state.config[key] || "";
    }
  });
}

function renderCases() {
  $("caseTable").innerHTML = state.cases
    .map(
      (item) => `
        <label class="case-row">
          <input type="checkbox" class="case-checkbox" value="${escapeHtml(item.id)}" checked />
          <div>
            <h3>${escapeHtml(item.title)}</h3>
            <div class="muted">${escapeHtml(item.id)} | ${escapeHtml(item.module)} | ${escapeHtml(item.expected)}</div>
            <div class="chip-line">
              <span class="chip">${escapeHtml(item.priority)}</span>
              ${(item.tags || []).map((tag) => `<span class="chip">${escapeHtml(tag)}</span>`).join("")}
            </div>
          </div>
          <span class="muted">Selected</span>
        </label>
      `
    )
    .join("");
}

function renderRuns() {
  const options = ['<option value="">No Related Run</option>'].concat(
    state.runs.map((run) => `<option value="${escapeHtml(run.id)}">${escapeHtml(run.id)} | ${escapeHtml(run.name)}</option>`)
  );
  $("relatedRunId").innerHTML = options.join("");

  $("runList").innerHTML = state.runs.length
    ? state.runs
        .map(
          (run) => `
            <div class="card-row">
              <div class="section-head compact">
                <div>
                  <h3>${escapeHtml(run.name)}</h3>
                  <div class="muted">${escapeHtml(run.id)} | ${escapeHtml(run.environment)} | ${escapeHtml(run.startedAt)}</div>
                </div>
                <span class="status-pill ${escapeHtml(run.status)}">${escapeHtml(run.status)}</span>
              </div>
              <div class="muted">Command: ${escapeHtml(run.command)}</div>
              <div class="chip-line">
                <span class="chip">Total ${run.summary.total}</span>
                <span class="chip">Passed ${run.summary.passed}</span>
                <span class="chip">Failed ${run.summary.failed}</span>
                <span class="chip">Duration ${escapeHtml(run.duration)}</span>
              </div>
            </div>
          `
        )
        .join("")
    : '<div class="muted">No run records yet.</div>';
}

function renderBugs() {
  $("bugList").innerHTML = state.bugs.length
    ? state.bugs
        .map(
          (bug) => `
            <div class="card-row">
              <h3>${escapeHtml(bug.title)}</h3>
              <div class="muted">${escapeHtml(bug.id)} | Module ${escapeHtml(bug.module || "-")} | Severity ${escapeHtml(bug.severity)}</div>
              <div class="chip-line">
                <span class="chip">Priority ${escapeHtml(bug.priority)}</span>
                <span class="chip">Run ${escapeHtml(bug.relatedRunId || "-")}</span>
                <span class="chip">Status ${escapeHtml(bug.zentaoStatus)}</span>
              </div>
              <div class="muted">Submit Preview: ${escapeHtml(bug.commandPreview)}</div>
            </div>
          `
        )
        .join("")
    : '<div class="muted">No bug records yet.</div>';
}

function syncView() {
  fillConfig();
  renderMetrics();
  renderCases();
  renderRuns();
  renderBugs();
}

async function loadDashboard() {
  const data = await request("/api/dashboard");
  state.config = data.config;
  state.cases = data.cases;
  state.runs = data.runs;
  state.bugs = data.bugs;
  syncView();
}

async function saveConfig() {
  const nextConfig = Object.fromEntries(
    configFields
      .filter((key) => $(key))
      .map((key) => [key, $(key).value.trim()])
  );
  const data = await request("/api/config", {
    method: "POST",
    body: JSON.stringify(nextConfig)
  });
  state.config = data.config;
  syncView();
  window.alert("Configuration saved");
}

async function testZentao() {
  const nextConfig = Object.fromEntries(
    configFields
      .filter((key) => $(key))
      .map((key) => [key, $(key).value.trim()])
  );
  const output = $("commandOutput");
  output.textContent = "Testing ZenTao connection...";
  const data = await request("/api/zentao/test", {
    method: "POST",
    body: JSON.stringify(nextConfig)
  });
  output.textContent = JSON.stringify(data, null, 2);
}

async function runCases() {
  const caseIds = Array.from(document.querySelectorAll(".case-checkbox:checked")).map((item) => item.value);
  if (caseIds.length === 0) {
    window.alert("Select at least one test case");
    return;
  }

  const data = await request("/api/runs", {
    method: "POST",
    body: JSON.stringify({
      name: $("runName").value.trim(),
      environment: $("environment").value,
      executor: $("executor").value.trim(),
      caseIds
    })
  });

  state.runs.unshift(data.run);
  syncView();
  const failedCases = data.run.results.filter((item) => item.status === "failed");
  if (failedCases[0]) {
    $("bugTitle").value = `${failedCases[0].title} failed`;
    $("bugModule").value = failedCases[0].title.split(" ")[0] || "";
    $("bugActual").value = failedCases[0].actual;
    $("bugSteps").value = `1. Open run ${data.run.id}\n2. Review case ${failedCases[0].caseId}\n3. Reproduce the failure`;
    $("bugExpected").value = "Actual result should match expected behavior";
    $("relatedRunId").value = data.run.id;
  }
}

async function submitBug(submitToZentao) {
  const payload = {
    title: $("bugTitle").value.trim(),
    module: $("bugModule").value.trim(),
    severity: $("bugSeverity").value,
    priority: $("bugPriority").value,
    steps: $("bugSteps").value.trim(),
    expected: $("bugExpected").value.trim(),
    actual: $("bugActual").value.trim(),
    assignedTo: $("assignedTo").value.trim(),
    relatedRunId: $("relatedRunId").value,
    submitToZentao
  };
  const data = await request("/api/bugs", {
    method: "POST",
    body: JSON.stringify(payload)
  });
  state.bugs.unshift(data.bug);
  renderMetrics();
  renderBugs();
  window.alert(submitToZentao ? "Bug submitted to ZenTao" : "Bug saved locally");
}

async function previewCommand() {
  const command = $("automationCommand").value.trim();
  const output = $("commandOutput");
  output.textContent = "Running command...";
  const data = await request("/api/command-preview", {
    method: "POST",
    body: JSON.stringify({ command })
  });
  output.textContent = `ok: ${data.ok}\ncode: ${data.code || 0}\n\nstdout:\n${data.stdout || "(empty)"}\n\nstderr:\n${data.stderr || "(empty)"}`;
}

function bindEvents() {
  $("saveConfigBtn").addEventListener("click", saveConfig);
  $("testZentaoBtn").addEventListener("click", testZentao);
  $("runCasesBtn").addEventListener("click", runCases);
  $("saveBugBtn").addEventListener("click", () => submitBug(false));
  $("submitBugBtn").addEventListener("click", () => submitBug(true));
  $("previewCmdBtn").addEventListener("click", previewCommand);
}

bindEvents();
loadDashboard().catch((error) => {
  $("commandOutput").textContent = error.message;
});
