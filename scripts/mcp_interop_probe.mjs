/* Dev-only interop probe: validates eggcalc's dual-era MCP transcripts
 * against the official @modelcontextprotocol/core wire schemas (v2 SDK,
 * bundled with the published MCP Inspector). Not part of the test suite;
 * requires Node 20+. See docs/mcp.md "Interoperability" for the command.
 *
 * Usage: MCP_CORE_DIR=<path-to-core> node scripts/mcp_interop_probe.mjs <server-command...>
 * Example: MCP_CORE_DIR="$CORE" node scripts/mcp_interop_probe.mjs .venv/bin/python -m eggcalc --mcp
 */
import { spawn } from "node:child_process";
import { createRequire } from "node:module";

const CORE_DIR =
  process.env.MCP_CORE_DIR ??
  `${process.env.HOME}/.npm/_npx/5a9d879542beca3a/node_modules/@modelcontextprotocol/core`;
const require = createRequire(`${CORE_DIR}/package.json`);
const core = require(CORE_DIR);

const {
  DiscoverResultSchema,
  ListToolsResultSchema,
  CallToolResultSchema,
  InitializeResultSchema,
} = core;

const META = {
  "io.modelcontextprotocol/protocolVersion": "2026-07-28",
  "io.modelcontextprotocol/clientCapabilities": {},
  "io.modelcontextprotocol/clientInfo": { name: "interop-probe", version: "0.0.1" },
};

const requests = [
  { jsonrpc: "2.0", id: 1, method: "server/discover", params: { _meta: META } },
  { jsonrpc: "2.0", id: 2, method: "tools/list", params: { _meta: META } },
  {
    jsonrpc: "2.0",
    id: 3,
    method: "tools/call",
    params: { name: "math_eval", arguments: { expression: "5+3" }, _meta: META },
  },
  {
    jsonrpc: "2.0",
    id: 4,
    method: "initialize",
    params: {
      protocolVersion: "2025-11-25",
      capabilities: {},
      clientInfo: { name: "interop-probe", version: "0.0.1" },
    },
  },
  { jsonrpc: "2.0", method: "notifications/initialized", params: {} },
  { jsonrpc: "2.0", id: 5, method: "tools/list", params: {} },
];

const [cmd, ...args] = process.argv.slice(2);
if (!cmd) {
  console.error("usage: node probe.mjs <server-command...>");
  process.exit(2);
}
const child = spawn(cmd, args, { stdio: ["pipe", "pipe", "inherit"] });
let out = "";
child.stdout.on("data", (d) => (out += d));
child.stdin.write(requests.map((r) => JSON.stringify(r)).join("\n") + "\n");
child.stdin.end();
await new Promise((resolve, reject) => {
  const t = setTimeout(() => reject(new Error("timeout waiting for server exit")), 60000);
  child.on("close", () => (clearTimeout(t), resolve()));
});

const responses = out.split("\n").filter(Boolean).map((l) => JSON.parse(l));
console.log(JSON.stringify({ requests, responses }, null, 2));

const byId = Object.fromEntries(responses.filter((r) => "id" in r).map((r) => [r.id, r]));
let failures = 0;
function check(label, schema, value) {
  if (value === undefined) {
    console.error(`FAIL ${label}: missing response`);
    failures++;
    return;
  }
  if (value.error) {
    console.error(`FAIL ${label}: got JSON-RPC error ${JSON.stringify(value.error)}`);
    failures++;
    return;
  }
  const parsed = schema.safeParse(value.result);
  if (!parsed.success) {
    console.error(`FAIL ${label}: ${parsed.error.message.slice(0, 2000)}`);
    failures++;
    return;
  }
  console.log(`PASS ${label}`);
}

check("modern server/discover", DiscoverResultSchema, byId[1]);
check("modern tools/list", ListToolsResultSchema, byId[2]);
check("modern tools/call", CallToolResultSchema, byId[3]);
check("legacy initialize", InitializeResultSchema, byId[4]);

// Legacy tools/list has no dedicated modern schema expectations; assert shape manually.
const legacyList = byId[5];
if (!legacyList?.result?.tools?.length) {
  console.error("FAIL legacy tools/list: no tools");
  failures++;
} else {
  console.log(`PASS legacy tools/list (${legacyList.result.tools.length} tools)`);
}

// Spot-check modern wire obligations the schemas may treat loosely.
const d = byId[1]?.result ?? {};
const problems = [];
if (d.resultType !== "complete") problems.push("discover.resultType");
if (!Array.isArray(d.supportedVersions) || !d.supportedVersions.includes("2026-07-28"))
  problems.push("discover.supportedVersions");
if (d.ttlMs === undefined || d.cacheScope === undefined) problems.push("discover cache hints");
if (d._meta?.["io.modelcontextprotocol/serverInfo"]?.name !== "eggcalc")
  problems.push("discover serverInfo _meta");
const call = byId[3]?.result ?? {};
if (call.resultType !== "complete") problems.push("call.resultType");
if (problems.length) {
  console.error(`FAIL modern wire obligations: ${problems.join(", ")}`);
  failures++;
} else {
  console.log("PASS modern wire obligations");
}

if (failures) {
  console.error(`${failures} interop check(s) failed`);
  process.exit(1);
}
console.log("All interop checks passed");
