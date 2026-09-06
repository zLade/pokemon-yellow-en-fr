#!/usr/bin/env node
/** Build the review workbook with artifact_tool and preserve feedback O:P. */

import fs from "node:fs/promises";
import path from "node:path";
import {
  FileBlob,
  SpreadsheetFile,
  Workbook,
} from "@oai/artifact-tool";

const EXPECTED_ROWS = 1056;
const EXPECTED_COLUMNS = 16;
const DATA_LAST_ROW = EXPECTED_ROWS;
const VERDICTS = [
  "Validé",
  "À revoir",
  "À réécrire",
  "Erreur de sens",
  "Découpage à revoir",
];

function argumentsFromCommandLine(argv) {
  const options = new Map();
  for (let index = 0; index < argv.length; index += 2) {
    const key = argv[index];
    const value = argv[index + 1];
    if (!key?.startsWith("--") || value === undefined) {
      throw new Error(`Argument incomplet : ${key ?? "<absent>"}`);
    }
    options.set(key.slice(2), value);
  }
  for (const required of ["csv", "output", "preview-dir"]) {
    if (!options.has(required)) {
      throw new Error(`--${required} est obligatoire`);
    }
  }
  return {
    csv: options.get("csv"),
    existing: options.get("existing") ?? "",
    output: options.get("output"),
    previewDir: options.get("preview-dir"),
  };
}

function assertCanonicalRows(values, label) {
  const rows = values.length;
  const columns = values[0]?.length ?? 0;
  if (rows !== EXPECTED_ROWS || columns !== EXPECTED_COLUMNS) {
    throw new Error(
      `${label} : ${rows}x${columns}, ` +
      `${EXPECTED_ROWS}x${EXPECTED_COLUMNS} attendu`,
    );
  }
  for (let index = 1; index < values.length; index += 1) {
    const expectedId = `D${String(index).padStart(4, "0")}`;
    if (values[index][0] !== expectedId) {
      throw new Error(
        `${label} : ID ligne ${index + 1} = ${values[index][0]}, ` +
        `${expectedId} attendu`,
      );
    }
  }
  const keys = values.slice(1).map((row) => row[1]);
  if (keys.some((key) => !key) || new Set(keys).size !== keys.length) {
    throw new Error(`${label} : clés stables vides ou dupliquées`);
  }
}

async function preservedFeedback(existingPath) {
  const feedback = new Map();
  if (!existingPath) return feedback;
  try {
    await fs.access(existingPath);
  } catch {
    return feedback;
  }
  const input = await FileBlob.load(existingPath);
  const workbook = await SpreadsheetFile.importXlsx(input);
  if (workbook.worksheets.items.length !== 1) {
    throw new Error("Le classeur existant doit contenir une seule feuille");
  }
  const values = workbook.worksheets.getItemAt(0).getUsedRange().values;
  if ((values[0]?.length ?? 0) < EXPECTED_COLUMNS) {
    throw new Error("Le classeur existant ne contient pas O:P");
  }
  for (const row of values.slice(1)) {
    const key = row[1];
    const verdict = row[14] ?? "";
    const comment = row[15] ?? "";
    if (key && (verdict !== "" || comment !== "")) {
      feedback.set(key, [verdict, comment]);
    }
  }
  return feedback;
}

function applyFeedback(values, feedback) {
  let preserved = 0;
  for (const row of values.slice(1)) {
    const prior = feedback.get(row[1]);
    if (!prior) continue;
    [row[14], row[15]] = prior;
    preserved += 1;
  }
  return preserved;
}

function applyConditionalFormatting(sheet) {
  const confidence = sheet.getRange(`K2:K${DATA_LAST_ROW}`);
  for (const [text, fill, color] of [
    ["high", "#C6EFCE", "#006100"],
    ["source directe", "#DDEBF7", "#1F4E78"],
    ["medium", "#FFEB9C", "#9C6500"],
    ["low", "#FFC7CE", "#9C0006"],
  ]) {
    confidence.conditionalFormats.add("containsText", {
      text,
      format: { fill, font: { bold: true, color } },
    });
  }

  const verdict = sheet.getRange(`O2:O${DATA_LAST_ROW}`);
  for (const [text, fill, color] of [
    ["Validé", "#C6EFCE", "#006100"],
    ["À revoir", "#FFEB9C", "#9C6500"],
    ["À réécrire", "#FFC7CE", "#9C0006"],
    ["Erreur de sens", "#F4CCCC", "#990000"],
    ["Découpage à revoir", "#FCE5CD", "#B45F06"],
  ]) {
    verdict.conditionalFormats.add("containsText", {
      text,
      format: { fill, font: { bold: true, color } },
    });
  }
}

function applyLayout(sheet) {
  sheet.showGridLines = false;
  sheet.freezePanes.freezeRows(1);
  sheet.freezePanes.freezeColumns(2);

  const all = sheet.getRange(`A1:P${DATA_LAST_ROW}`);
  all.format = {
    font: { name: "Arial", size: 10, color: "#172033" },
    verticalAlignment: "top",
  };
  all.format.borders = {
    preset: "all",
    style: "thin",
    color: "#D9E1E8",
  };
  sheet.getRange(`H1:P${DATA_LAST_ROW}`).format.wrapText = true;

  const header = sheet.getRange("A1:P1");
  header.format = {
    fill: "#1F4E78",
    font: { name: "Arial", size: 10, bold: true, color: "#FFFFFF" },
    verticalAlignment: "center",
    horizontalAlignment: "center",
    wrapText: true,
    rowHeightPx: 42,
  };

  const widths = [
    ["A", 72], ["B", 168], ["C", 132], ["D", 112],
    ["E", 82], ["F", 150], ["G", 120], ["H", 330],
    ["I", 330], ["J", 330], ["K", 112], ["L", 260],
    ["M", 96], ["N", 132], ["O", 160], ["P", 300],
  ];
  for (const [column, pixels] of widths) {
    sheet.getRange(`${column}1:${column}${DATA_LAST_ROW}`).format.columnWidthPx =
      pixels;
  }
  sheet.getRange(`A2:P${DATA_LAST_ROW}`).format.autofitRows();

  const feedback = sheet.getRange(`O1:P${DATA_LAST_ROW}`);
  feedback.format.fill = "#FFF8E1";
  sheet.getRange("O1:P1").format = {
    fill: "#7F6000",
    font: { name: "Arial", size: 10, bold: true, color: "#FFFFFF" },
    verticalAlignment: "center",
    horizontalAlignment: "center",
    wrapText: true,
  };
}

async function renderRange(workbook, sheetName, range, destination) {
  const blob = await workbook.render({
    sheetName,
    range,
    scale: 1,
    format: "png",
  });
  await fs.writeFile(destination, new Uint8Array(await blob.arrayBuffer()));
}

const args = argumentsFromCommandLine(process.argv.slice(2));
await fs.mkdir(path.dirname(args.output), { recursive: true });
await fs.mkdir(args.previewDir, { recursive: true });

const csvText = (await fs.readFile(args.csv, "utf8")).replace(/^\uFEFF/, "");
const workbook = await Workbook.fromCSV(csvText, { sheetName: "Dialogues" });
const sheet = workbook.worksheets.getItemAt(0);
const values = sheet.getUsedRange().values;
assertCanonicalRows(values, "CSV importé");

const feedback = await preservedFeedback(args.existing);
const feedbackCount = applyFeedback(values, feedback);
sheet.getRangeByIndexes(0, 0, EXPECTED_ROWS, EXPECTED_COLUMNS).writeValues(values);

applyLayout(sheet);
const table = sheet.tables.add(
  `A1:P${DATA_LAST_ROW}`,
  true,
  "DialogueReviewTable",
);
table.showFilterButton = true;
table.showBandedColumns = false;
sheet.getRange(`O2:O${DATA_LAST_ROW}`).dataValidation = {
  allowBlank: true,
  list: { inCellDropDown: true, source: VERDICTS },
};
applyConditionalFormatting(sheet);

const finalValues = sheet.getUsedRange().values;
assertCanonicalRows(finalValues, "Classeur final");
for (let row = 0; row < EXPECTED_ROWS; row += 1) {
  for (let column = 0; column < EXPECTED_COLUMNS; column += 1) {
    if ((finalValues[row][column] ?? "") !== (values[row][column] ?? "")) {
      throw new Error(`Valeur divergente à ${row + 1},${column + 1}`);
    }
  }
}

const inspection = await workbook.inspect({
  kind: "workbook,sheet,table,computedStyle",
  sheetId: sheet.name,
  range: "A1:P8",
  maxChars: 12000,
  tableMaxRows: 8,
  tableMaxCols: 16,
});
await fs.writeFile(
  path.join(args.previewDir, "review_workbook.inspect.ndjson"),
  inspection.ndjson,
  "utf8",
);
const formulaErrors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#SPILL!|#CALC!",
  options: { useRegex: true, maxResults: 100 },
  summary: "dialogue review formula error scan",
});
if (/"matchCount"\s*:\s*[1-9]/.test(formulaErrors.ndjson)) {
  throw new Error("Erreur de cellule détectée dans le classeur");
}

await renderRange(
  workbook,
  sheet.name,
  "A1:P18",
  path.join(args.previewDir, "review_workbook_top.png"),
);
await renderRange(
  workbook,
  sheet.name,
  "A1048:P1056",
  path.join(args.previewDir, "review_workbook_bottom.png"),
);

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(args.output);
console.log(
  `XLSX PASS rows=${EXPECTED_ROWS} columns=${EXPECTED_COLUMNS} ` +
  `feedback=${feedbackCount} output=${args.output}`,
);
