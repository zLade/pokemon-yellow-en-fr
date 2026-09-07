#!/usr/bin/env node
/** Test review helpers without installing the optional workbook renderer. */

import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import test from "node:test";

const source = fs.readFileSync(new URL("./build_dialogue_review_xlsx.mjs", import.meta.url), "utf8");
const helpers = source.split("const args = argumentsFromCommandLine(")[0]
  .replace(/^import[\s\S]*?;\s*/gm, "");
const context = vm.createContext({});
vm.runInContext(`${helpers}\nglobalThis.helpers = {
  EXPECTED_HEADERS, VERDICTS, argumentsFromCommandLine, assertCanonicalRows,
  applyFeedback, applyConditionalFormatting, normalizeVerdict,
};`, context);
const api = context.helpers;

function canonicalRows() {
  const rows = [Array.from(api.EXPECTED_HEADERS)];
  for (let index = 1; index <= 1055; index += 1) {
    const row = Array(16).fill("");
    row[0] = `D${String(index).padStart(4, "0")}`;
    row[1] = `MAIN:0x${index.toString(16).toUpperCase().padStart(6, "0")}`;
    rows.push(row);
  }
  return rows;
}

test("English schema validates every row and rejects old headers", () => {
  const rows = canonicalRows();
  api.assertCanonicalRows(rows, "Imported CSV");
  rows[0][1] = "cle_stable";
  assert.throws(() => api.assertCanonicalRows(rows, "Imported CSV"), /English column headers/);
  rows[0][1] = "stable_key";
  rows[1].pop();
  assert.throws(() => api.assertCanonicalRows(rows, "Imported CSV"), /row 2 must have 16 columns/);
});

test("invalid arguments, IDs and keys have English diagnostics", () => {
  assert.throws(() => api.argumentsFromCommandLine(["--csv"]), /Incomplete argument/);
  assert.throws(() => api.argumentsFromCommandLine([]), /--csv is required/);
  const rows = canonicalRows();
  rows[1][0] = "invalid";
  assert.throws(() => api.assertCanonicalRows(rows, "Imported CSV"), /ID in row 2.*D0001 expected/);
  rows[1][0] = "D0001";
  rows[2][1] = rows[1][1];
  assert.throws(() => api.assertCanonicalRows(rows, "Imported CSV"), /empty or duplicate stable keys/);
});

test("legacy verdicts become English without changing dialogue or comments", () => {
  const legacy = ["Validé", "À revoir", "À réécrire", "Erreur de sens", "Découpage à revoir"];
  assert.deepEqual(Array.from(api.VERDICTS), [
    "Approved", "Needs review", "Rewrite required", "Meaning error", "Layout review",
  ]);
  const rows = canonicalRows();
  const feedback = new Map();
  for (let index = 0; index < legacy.length; index += 1) {
    rows[index + 1][7] = "Un Pokémon sauvage apparaît !";
    rows[index + 1][8] = "你好！";
    feedback.set(rows[index + 1][1], [legacy[index], ` Keep comment ${index}\n `]);
  }
  rows[6][14] = "Validé";
  assert.equal(api.applyFeedback(rows, feedback), 5);
  for (let index = 0; index < legacy.length; index += 1) {
    assert.equal(rows[index + 1][14], api.VERDICTS[index]);
    assert.equal(rows[index + 1][15], ` Keep comment ${index}\n `);
    assert.equal(rows[index + 1][7], "Un Pokémon sauvage apparaît !");
    assert.equal(rows[index + 1][8], "你好！");
  }
  assert.equal(rows[6][14], "Approved");
  assert.equal(api.normalizeVerdict("Custom feedback"), "Custom feedback");
});

test("conditional formatting matches English confidence and verdict values", () => {
  const rules = new Map();
  api.applyConditionalFormatting({
    getRange(range) {
      rules.set(range, []);
      return { conditionalFormats: { add(type, options) {
        assert.equal(type, "containsText");
        rules.get(range).push(options.text);
      } } };
    },
  });
  assert.deepEqual(rules.get("K2:K1056"), ["high", "direct source", "medium", "low"]);
  assert.deepEqual(rules.get("O2:O1056"), Array.from(api.VERDICTS));
});
