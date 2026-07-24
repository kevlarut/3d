#!/usr/bin/env node
/*
 * npm run generate  ->  turn the Mixamo FBX files in a character folder into a
 * Diablo-style sprite sheet, with no manual Blender work.
 *
 * Usage:
 *   cd hobbit-female && npm run generate          # "the folder I'm in"
 *   npm run generate -- hobbit-female             # explicit folder
 *
 * Finding Blender (first that works wins):
 *   1. $BLENDER                                   env var -> a blender binary
 *   2. `blender` on PATH
 *   3. /Applications/Blender.app/Contents/MacOS/Blender   (macOS default)
 *   4. $SPRITE_PYTHON                             a python that has `bpy`
 *      installed (headless fallback, no Blender app needed)
 */

import { spawnSync, spawnSync as _s } from "node:child_process";
import { existsSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve, basename, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(__dirname, "..");
const PIPELINE = join(__dirname, "pipeline.py");

function fail(msg) {
  console.error(`\n[generate] ${msg}\n`);
  process.exit(1);
}

// ---- resolve the target folder -------------------------------------------
// npm sets INIT_CWD to the directory the user ran the command from.
const argFolder = process.argv[2];
const folderInput = argFolder || process.env.INIT_CWD || process.cwd();
const folder = resolve(REPO_ROOT, folderInput);

if (!existsSync(folder) || !statSync(folder).isDirectory()) {
  fail(`folder not found: ${folder}`);
}
if (folder === REPO_ROOT) {
  fail(
    "run this from inside a character folder, e.g.\n" +
      "  cd hobbit-female && npm run generate\n" +
      "or pass one:  npm run generate -- hobbit-female"
  );
}
console.log(`[generate] character folder: ${basename(folder)}`);

// ---- resolve how to run Blender ------------------------------------------
function isRunnable(p) {
  try {
    return p && existsSync(p) && statSync(p).isFile();
  } catch {
    return false;
  }
}

const candidates = [];
if (process.env.BLENDER) candidates.push({ kind: "blender", bin: process.env.BLENDER });
candidates.push({ kind: "blender", bin: "blender" }); // PATH lookup
candidates.push({
  kind: "blender",
  bin: "/Applications/Blender.app/Contents/MacOS/Blender",
});

function blenderWorks(bin) {
  if (bin !== "blender" && !isRunnable(bin)) return false;
  const r = _s(bin, ["--version"], { stdio: "ignore" });
  return r.status === 0;
}

let runner = null;
for (const c of candidates) {
  if (c.kind === "blender" && blenderWorks(c.bin)) {
    runner = c;
    break;
  }
}
if (!runner && process.env.SPRITE_PYTHON && isRunnable(process.env.SPRITE_PYTHON)) {
  runner = { kind: "python", bin: process.env.SPRITE_PYTHON };
}

if (!runner) {
  fail(
    "could not find Blender. Do one of:\n" +
      "  * install Blender 4.2+ and put it on PATH, or\n" +
      "  * set BLENDER=/path/to/blender, or\n" +
      "  * set SPRITE_PYTHON=/path/to/python-with-bpy (pip install bpy)"
  );
}

// ---- run it ---------------------------------------------------------------
const pyArgs = ["--folder", folder, "--root", REPO_ROOT];
let cmd, args;
if (runner.kind === "blender") {
  cmd = runner.bin;
  args = ["--background", "--factory-startup", "--python", PIPELINE, "--", ...pyArgs];
  console.log(`[generate] using Blender: ${runner.bin}`);
} else {
  cmd = runner.bin;
  args = [PIPELINE, ...pyArgs];
  console.log(`[generate] using bpy python: ${runner.bin}`);
}

const res = spawnSync(cmd, args, { stdio: "inherit", cwd: REPO_ROOT });
if (res.error) fail(`failed to launch: ${res.error.message}`);
process.exit(res.status ?? 1);
