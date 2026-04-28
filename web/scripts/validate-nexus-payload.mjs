import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import Ajv from "ajv";
import addFormats from "ajv-formats";

const repoRoot = path.resolve(path.dirname(new URL(import.meta.url).pathname), "../..");
const schemaPath = path.join(repoRoot, "src", "api", "schema", "nexus_payload.json");
const fixturePath = path.join(repoRoot, "web", "src", "data", "mock-traces.json");

function readJson(p) {
  return JSON.parse(fs.readFileSync(p, "utf8"));
}

const schema = readJson(schemaPath);
const payload = readJson(fixturePath);

const ajv = new Ajv({
  allErrors: true,
  strict: false,
});
addFormats(ajv);

const validate = ajv.compile(schema);
const ok = validate(payload);

if (ok) {
  console.log("OK: mock-traces.json matches src/api/schema/nexus_payload.json");
  process.exit(0);
}

console.error("ERROR: mock-traces.json does not match src/api/schema/nexus_payload.json");
for (const err of validate.errors ?? []) {
  const where = err.instancePath || "<root>";
  console.error(`- ${where}: ${err.message}`);
}
process.exit(1);
