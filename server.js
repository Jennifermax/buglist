const http = require("http");
const https = require("https");
const fs = require("fs");
const path = require("path");
const { exec } = require("child_process");

const HOST = "127.0.0.1";
const PORT = process.env.PORT || 3000;
const ROOT = __dirname;
const PUBLIC_DIR = path.join(ROOT, "public");
const DATA_DIR = path.join(ROOT, "data");
const CONFIG_FILE = path.join(DATA_DIR, "config.json");
const CASES_FILE = path.join(DATA_DIR, "test-cases.json");
const RUNS_FILE = path.join(DATA_DIR, "runs.json");
const BUGS_FILE = path.join(DATA_DIR, "bugs.json");

const contentTypes = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8"
};

function ensureDataFile(file, fallback) {
  if (!fs.existsSync(file)) {
    fs.writeFileSync(file, JSON.stringify(fallback, null, 2), "utf8");
  }
}

function readJson(file, fallback) {
  ensureDataFile(file, fallback);
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function writeJson(file, value) {
  fs.writeFileSync(file, JSON.stringify(value, null, 2), "utf8");
}

function sendJson(res, statusCode, payload) {
  const body = JSON.stringify(payload);
  res.writeHead(statusCode, {
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": Buffer.byteLength(body)
  });
  res.end(body);
}

function readRequestBody(req) {
  return new Promise((resolve, reject) => {
    let body = "";
    req.on("data", (chunk) => {
      body += chunk;
      if (body.length > 10 * 1024 * 1024) {
        reject(new Error("Request body too large"));
      }
    });
    req.on("end", () => {
      if (!body) {
        resolve({});
        return;
      }

      try {
        resolve(JSON.parse(body));
      } catch (error) {
        reject(new Error("Invalid JSON payload"));
      }
    });
    req.on("error", reject);
  });
}

function toArray(value) {
  return Array.isArray(value) ? value : [];
}

function parseMaybeJson(text) {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function parseNestedData(value) {
  if (typeof value === "string") {
    return parseMaybeJson(value) || value;
  }
  return value;
}

function normalizeBaseUrl(value) {
  return String(value || "").replace(/\/+$/, "");
}

function buildPageApiBase(baseUrl) {
  return normalizeBaseUrl(baseUrl).replace(/\/api\.php(?:\/v1)?$/i, "");
}

function createHttpClient(urlString, options) {
  const url = new URL(urlString);
  return new Promise((resolve, reject) => {
    const lib = url.protocol === "https:" ? https : http;
    const request = lib.request(
      url,
      {
        method: options.method || "GET",
        headers: options.headers || {},
        rejectUnauthorized: options.rejectUnauthorized !== false
      },
      (response) => {
        let body = "";
        response.setEncoding("utf8");
        response.on("data", (chunk) => {
          body += chunk;
        });
        response.on("end", () => {
          resolve({
            statusCode: response.statusCode || 0,
            headers: response.headers,
            body
          });
        });
      }
    );

    request.on("error", reject);
    request.setTimeout(options.timeoutMs || 15000, () => {
      request.destroy(new Error("Request timeout"));
    });

    if (options.body) {
      request.write(options.body);
    }
    request.end();
  });
}

async function fetchJson(url, options = {}) {
  const response = await createHttpClient(url, options);
  const parsed = parseMaybeJson(response.body);
  return {
    statusCode: response.statusCode,
    headers: response.headers,
    data: parsed,
    rawBody: response.body
  };
}

function serveStatic(req, res) {
  const parsedPath = new URL(req.url, `http://${req.headers.host}`).pathname;
  const relativePath = parsedPath === "/" ? "/index.html" : parsedPath;
  const filePath = path.normalize(path.join(PUBLIC_DIR, relativePath));

  if (!filePath.startsWith(PUBLIC_DIR)) {
    sendJson(res, 403, { error: "Forbidden" });
    return;
  }

  fs.readFile(filePath, (error, file) => {
    if (error) {
      if (error.code === "ENOENT") {
        sendJson(res, 404, { error: "Not found" });
        return;
      }
      sendJson(res, 500, { error: "Failed to read file" });
      return;
    }

    res.writeHead(200, {
      "Content-Type": contentTypes[path.extname(filePath)] || "text/plain; charset=utf-8"
    });
    res.end(file);
  });
}

function createRun(payload) {
  const config = readJson(CONFIG_FILE, {});
  const cases = readJson(CASES_FILE, []);
  const runs = readJson(RUNS_FILE, []);
  const selectedCases = cases.filter((item) => toArray(payload.caseIds).includes(item.id));
  const id = `RUN-${Date.now()}`;
  const startedAt = new Date().toISOString();
  const duration = `${5 + selectedCases.length * 2}s`;

  const results = selectedCases.map((item, index) => {
    const passed = (index + item.id.length) % 3 !== 0;
    return {
      caseId: item.id,
      title: item.title,
      status: passed ? "passed" : "failed",
      duration: `${2 + index}s`,
      actual: passed ? "Actual result matches expected behavior" : "Validation failed, logs collected",
      evidence: passed ? [] : ["screenshot.png", "network.log"]
    };
  });

  const summary = results.reduce(
    (acc, item) => {
      acc.total += 1;
      acc[item.status] += 1;
      return acc;
    },
    { total: 0, passed: 0, failed: 0 }
  );

  const run = {
    id,
    name: payload.name || `Hackathon Run ${new Date().toLocaleString("zh-CN", { hour12: false })}`,
    environment: payload.environment || "staging",
    executor: payload.executor || "system",
    command: payload.command || config.automationCommand || "npm run e2e",
    zentaoProductId: payload.zentaoProductId || config.zentaoProductId || "",
    startedAt,
    duration,
    status: summary.failed > 0 ? "failed" : "passed",
    summary,
    results
  };

  runs.unshift(run);
  writeJson(RUNS_FILE, runs);
  return run;
}

function mapBugPayload(config, payload) {
  const title = String(payload.title || "").trim();
  const steps = String(payload.steps || "").trim();
  const expected = String(payload.expected || "").trim();
  const actual = String(payload.actual || "").trim();
  const openedBuild = String(payload.openedBuild || config.zentaoOpenedBuild || "trunk").trim();
  const assignedTo = String(payload.assignedTo || "").trim();
  const severity = String(payload.severity || "2");
  const priority = String(payload.priority || "2");
  const module = String(payload.module || "").trim();
  const moduleId = String(payload.moduleId || config.zentaoModuleId || "").trim();
  const productId = String(payload.productId || config.zentaoProductId || "").trim();
  const projectId = String(payload.projectId || config.zentaoProjectId || "").trim();

  return {
    id: `BUG-${Date.now()}`,
    title,
    severity,
    priority,
    module,
    moduleId,
    productId,
    projectId,
    steps,
    expected,
    actual,
    assignedTo,
    openedBuild,
    relatedRunId: payload.relatedRunId || "",
    zentaoStatus: "pending",
    zentaoEndpoint: normalizeBaseUrl(config.zentaoBaseUrl || ""),
    createdAt: new Date().toISOString(),
    commandPreview: ""
  };
}

function buildOpenApiHeaders(config) {
  const headers = {
    "Content-Type": "application/json",
    Accept: "application/json"
  };
  if (config.zentaoToken) {
    headers.Token = config.zentaoToken;
  }
  return headers;
}

async function submitBugByOpenApi(config, bug) {
  const baseUrl = normalizeBaseUrl(config.zentaoBaseUrl || "");
  const productId = bug.productId || config.zentaoProductId;
  if (!baseUrl || !productId || !config.zentaoToken) {
    throw new Error("OpenAPI requires base URL, product ID and Token");
  }

  const endpoint = `${baseUrl}/api.php/v1/products/${encodeURIComponent(productId)}/bugs`;
  const body = JSON.stringify({
    title: bug.title,
    steps: bug.steps,
    task: 0,
    type: "codeerror",
    severity: Number(bug.severity),
    pri: Number(bug.priority),
    module: bug.moduleId ? Number(bug.moduleId) : 0,
    project: bug.projectId ? Number(bug.projectId) : 0,
    assignedTo: bug.assignedTo || "",
    openedBuild: [bug.openedBuild || "trunk"]
  });

  const response = await fetchJson(endpoint, {
    method: "POST",
    headers: buildOpenApiHeaders(config),
    body
  });

  const ok = response.statusCode >= 200 && response.statusCode < 300;
  return {
    ok,
    endpoint,
    requestMode: "openapi",
    responseBody: response.data || response.rawBody
  };
}

function extractSessionInfo(data) {
  const candidates = [
    data,
    data && parseNestedData(data.data),
    data && data.session,
    data && parseNestedData(data.data) && parseNestedData(data.data).session
  ].filter(Boolean);

  for (const item of candidates) {
    const sessionName = item.sessionName || item.name;
    const sessionId = item.sessionID || item.sessionId || item.id;
    if (sessionName && sessionId) {
      return { sessionName, sessionId };
    }
  }
  return null;
}

function isSuccessfulLogin(data) {
  if (!data) return false;
  if (data.status && String(data.status).toLowerCase() === "success") return true;
  if (data.result && String(data.result).toLowerCase() === "success") return true;
  if (data.account) return true;
  if (data.userName) return true;
  return false;
}

async function getSessionCookie(baseUrl, account, password) {
  const apiBase = buildPageApiBase(baseUrl);
  const sessionResponse = await fetchJson(`${apiBase}/api-getsessionid.json`);
  const sessionInfo = extractSessionInfo(sessionResponse.data);
  if (!sessionInfo) {
    throw new Error("Failed to get ZenTao session information");
  }

  const body = new URLSearchParams({
    account,
    password
  }).toString();

  const loginResponse = await fetchJson(
    `${apiBase}/user-login.json?${encodeURIComponent(sessionInfo.sessionName)}=${encodeURIComponent(sessionInfo.sessionId)}`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        Accept: "application/json"
      },
      body
    }
  );

  if (!isSuccessfulLogin(loginResponse.data)) {
    throw new Error("ZenTao login failed, check account or password");
  }

  return `${sessionInfo.sessionName}=${sessionInfo.sessionId}`;
}

async function submitBugBySessionApi(config, bug) {
  const baseUrl = normalizeBaseUrl(config.zentaoBaseUrl || "");
  const productId = bug.productId || config.zentaoProductId;
  const account = String(config.zentaoAccount || "").trim();
  const password = String(config.zentaoPassword || "").trim();
  if (!baseUrl || !productId || !account || !password) {
    throw new Error("Session mode requires base URL, product ID, account and password");
  }

  const cookie = await getSessionCookie(baseUrl, account, password);
  const endpoint = `${buildPageApiBase(baseUrl)}/bug-create-${encodeURIComponent(productId)}.json`;
  const formBody = new URLSearchParams({
    title: bug.title,
    steps: bug.steps,
    assignedTo: bug.assignedTo || "",
    severity: bug.severity,
    pri: bug.priority,
    module: bug.moduleId || "0",
    project: bug.projectId || "0",
    openedBuild: bug.openedBuild || "trunk"
  }).toString();

  const response = await fetchJson(endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      Accept: "application/json",
      Cookie: cookie
    },
    body: formBody
  });

  const ok =
    (response.statusCode >= 200 && response.statusCode < 300) &&
    !(response.data && String(response.data.status || "").toLowerCase() === "fail");

  return {
    ok,
    endpoint,
    requestMode: "session",
    responseBody: response.data || response.rawBody
  };
}

function buildSubmitPreview(config, bug) {
  if (config.submitMode === "openapi") {
    return `POST ${normalizeBaseUrl(config.zentaoBaseUrl)}/api.php/v1/products/${bug.productId || config.zentaoProductId}/bugs`;
  }
  if (config.submitMode === "session") {
    return `POST ${buildPageApiBase(config.zentaoBaseUrl)}/bug-create-${bug.productId || config.zentaoProductId}.json`;
  }
  if (config.zentaoCliPath) {
    return `${config.zentaoCliPath} bug:create --title "${bug.title}"`;
  }
  return "Configure ZenTao API parameters before submitting";
}

async function createBug(payload) {
  const bugs = readJson(BUGS_FILE, []);
  const config = readJson(CONFIG_FILE, {});
  const bug = mapBugPayload(config, payload);
  bug.commandPreview = buildSubmitPreview(config, bug);

  if (payload.submitToZentao) {
    let submitResult;
    if (config.submitMode === "openapi") {
      submitResult = await submitBugByOpenApi(config, bug);
    } else if (config.submitMode === "session") {
      submitResult = await submitBugBySessionApi(config, bug);
    } else {
      throw new Error("Set submit mode to openapi or session before real submission");
    }

    bug.zentaoStatus = submitResult.ok ? "submitted" : "failed";
    bug.zentaoEndpoint = submitResult.endpoint;
    bug.submitResult = submitResult.responseBody;
  }

  bugs.unshift(bug);
  writeJson(BUGS_FILE, bugs);
  return bug;
}

function executeShell(payload) {
  return new Promise((resolve) => {
    if (!payload.command) {
      resolve({ ok: false, stdout: "", stderr: "No command provided" });
      return;
    }

    exec(
      payload.command,
      { cwd: ROOT, timeout: 60_000, windowsHide: true },
      (error, stdout, stderr) => {
        resolve({
          ok: !error,
          code: error && typeof error.code === "number" ? error.code : 0,
          stdout,
          stderr
        });
      }
    );
  });
}

async function testZentaoConnection(payload) {
  const config = readJson(CONFIG_FILE, {});
  const nextConfig = { ...config, ...payload };
  const baseUrl = normalizeBaseUrl(nextConfig.zentaoBaseUrl || "");
  if (!baseUrl) {
    throw new Error("ZenTao base URL is required");
  }

  if (nextConfig.submitMode === "openapi") {
    if (!nextConfig.zentaoProductId || !nextConfig.zentaoToken) {
      throw new Error("OpenAPI mode requires product ID and Token");
    }
    const endpoint = `${baseUrl}/api.php/v1/products/${encodeURIComponent(nextConfig.zentaoProductId)}/bugs?page=1&limit=1`;
    const response = await fetchJson(endpoint, {
      method: "GET",
      headers: buildOpenApiHeaders(nextConfig)
    });
    return {
      ok: response.statusCode >= 200 && response.statusCode < 300,
      mode: "openapi",
      endpoint,
      statusCode: response.statusCode,
      response: response.data || response.rawBody
    };
  }

  if (nextConfig.submitMode === "session") {
    if (!nextConfig.zentaoAccount || !nextConfig.zentaoPassword) {
      throw new Error("Session mode requires account and password");
    }
    const cookie = await getSessionCookie(baseUrl, nextConfig.zentaoAccount, nextConfig.zentaoPassword);
    return {
      ok: true,
      mode: "session",
      endpoint: `${buildPageApiBase(baseUrl)}/user-login.json`,
      statusCode: 200,
      response: { cookiePreview: cookie }
    };
  }

  throw new Error("Unknown submit mode");
}

async function handleApi(req, res) {
  const pathname = new URL(req.url, `http://${req.headers.host}`).pathname;

  if (req.method === "GET" && pathname === "/api/dashboard") {
    const cases = readJson(CASES_FILE, []);
    const runs = readJson(RUNS_FILE, []);
    const bugs = readJson(BUGS_FILE, []);
    const config = readJson(CONFIG_FILE, {});
    sendJson(res, 200, { config, cases, runs, bugs });
    return;
  }

  if (req.method === "POST" && pathname === "/api/config") {
    const payload = await readRequestBody(req);
    writeJson(CONFIG_FILE, payload);
    sendJson(res, 200, { ok: true, config: payload });
    return;
  }

  if (req.method === "POST" && pathname === "/api/test-cases") {
    const payload = await readRequestBody(req);
    const cases = Array.isArray(payload.cases) ? payload.cases : [];
    writeJson(CASES_FILE, cases);
    sendJson(res, 200, { ok: true, cases });
    return;
  }

  if (req.method === "POST" && pathname === "/api/runs") {
    const payload = await readRequestBody(req);
    const run = createRun(payload);
    sendJson(res, 200, { ok: true, run });
    return;
  }

  if (req.method === "POST" && pathname === "/api/bugs") {
    const payload = await readRequestBody(req);
    const required = ["title", "steps", "expected", "actual"];
    const missing = required.filter((key) => !payload[key]);
    if (missing.length > 0) {
      sendJson(res, 400, { error: `Missing fields: ${missing.join(", ")}` });
      return;
    }

    const bug = await createBug(payload);
    sendJson(res, 200, { ok: true, bug });
    return;
  }

  if (req.method === "POST" && pathname === "/api/zentao/test") {
    const payload = await readRequestBody(req);
    const result = await testZentaoConnection(payload);
    sendJson(res, 200, result);
    return;
  }

  if (req.method === "POST" && pathname === "/api/command-preview") {
    const payload = await readRequestBody(req);
    const result = await executeShell(payload);
    sendJson(res, 200, result);
    return;
  }

  sendJson(res, 404, { error: "API not found" });
}

function bootstrap() {
  ensureDataFile(CONFIG_FILE, {
    projectName: "Hackathon ZenTao Project",
    zentaoBaseUrl: "https://zt.codetech.pro/zentao",
    submitMode: "session",
    zentaoProductId: "",
    zentaoProjectId: "",
    zentaoModuleId: "",
    zentaoOpenedBuild: "trunk",
    zentaoToken: "",
    zentaoAccount: "",
    zentaoPassword: "",
    zentaoCliPath: "",
    automationCommand: "node scripts/mock-test-runner.js"
  });
  ensureDataFile(CASES_FILE, [
    {
      id: "CASE-LOGIN-001",
      module: "Login",
      title: "Account password login success",
      priority: "P1",
      tags: ["smoke", "web"],
      expected: "Homepage is visible after login"
    },
    {
      id: "CASE-ORDER-002",
      module: "Order",
      title: "Create order when inventory is available",
      priority: "P1",
      tags: ["regression", "api"],
      expected: "Order status becomes pending payment"
    },
    {
      id: "CASE-REPORT-003",
      module: "Report",
      title: "Refresh chart after changing filter",
      priority: "P2",
      tags: ["ui"],
      expected: "Chart and statistics cards update together"
    }
  ]);
  ensureDataFile(RUNS_FILE, []);
  ensureDataFile(BUGS_FILE, []);
}

bootstrap();

const server = http.createServer(async (req, res) => {
  try {
    if (req.url.startsWith("/api/")) {
      await handleApi(req, res);
      return;
    }
    serveStatic(req, res);
  } catch (error) {
    sendJson(res, 500, { error: error.message || "Internal server error" });
  }
});

server.listen(PORT, HOST, () => {
  console.log(`ZenTao bug system running at http://${HOST}:${PORT}`);
});
