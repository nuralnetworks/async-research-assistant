// Rebuild with the Codex bundled artifact runtime. Paths are supplied via env.
import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const { RUNTIME_NODE_MODULES, SKILL_DIR, RUNTIME_PYTHON, BUILD_DIR } = process.env;
const { Presentation, PresentationFile } = await import(pathToFileURL(
  path.join(RUNTIME_NODE_MODULES, '@oai/artifact-tool/dist/artifact_tool.mjs')));
const { finalizePresentation } = await import(pathToFileURL(
  path.join(SKILL_DIR, 'container_tools/artifact_tool_utils.mjs')));
await fs.mkdir(BUILD_DIR, { recursive: true });
const deck = Presentation.create({ slideSize: { width: 1280, height: 720 } });

function text(slide, value, x, y, width, height, size, color = '#19364A', bold = false) {
  const shape = slide.shapes.add({ geometry: 'textbox',
    position: { left: x, top: y, width, height },
    fill: 'none', line: { fill: 'none', width: 0 } });
  shape.text = value;
  shape.text.style = { typeface: 'Arial', fontSize: size, color, bold, autoFit: 'none' };
}

function slide(title, notes) {
  const item = deck.slides.add();
  item.background.fill = '#F7FAFC';
  text(item, title, 80, 64, 1120, 105, 48, '#153B57', true);
  item.speakerNotes.textFrame.setText(notes);
  return item;
}

let item = slide('Async Research Assistant',
  'Bailar contribution slides: title, CLI, deployment and Q&A. Insert the six slides authored by Nural, Emil and Mahammadali before the closing slide. Source: supplied team ownership rules.');
text(item, 'CLI and deployment', 80, 250, 1120, 90, 52, '#087E8B');
text(item, 'Nural · Emil · Mahammadali · Bailar', 80, 455, 1120, 50, 28);
text(item, 'AI-ENG-110 / Topic 4 / 18 September 2026', 80, 523, 1120, 50, 24);

item = slide('Command-line interface',
  'Owner: Bailar. Sources: researcher/cli.py and tests/test_cli.py. CLI unit tests fake Researcher. OfflineService uses canned references and a fake synthesizer. Synthetic reference URLs are demonstrations. Exit 2 is argparse validation; expected operational errors exit 1. Codex assisted implementation, tests and slide drafting.');
text(item, 'ask     demo     bench', 80, 185, 1120, 70, 40, '#087E8B', true);
text(item, 'Offline mode needs no API keys.\nJSON output keeps numbered citations and fetch timings.\nInvalid input returns a short error without a traceback.',
  80, 292, 1120, 160, 30);
text(item, '43 CLI + AI smoke tests passed\n94% CLI coverage in the full suite',
  80, 523, 1120, 105, 32, '#153B57', true);

item = slide('Docker and CI',
  'Owner: Bailar. Sources: Dockerfile, .dockerignore, .github/workflows/ci.yml and report/report.md. Both stages use python:3.12.6-slim. Appuser owns /app. All Docker steps passed in https://github.com/nuralnetworks/async-research-assistant/actions/runs/35284135541/job/105412575476 at head f090268. CI used --network none. Nural supplied the dependency fix in e03e8cf. Local Windows Docker and live provider runs are not claimed.');
text(item, 'Python 3.12.6 in two stages', 80, 190, 1120, 65, 38, '#087E8B', true);
text(item, 'The runtime uses a non-root account with writable outputs.\nCI checks lint, types, coverage and the Docker build.\nContainer smoke tests disable networking.',
  80, 290, 1120, 165, 30);
text(item, 'Docker build and offline runs passed', 80, 502, 1120, 50, 30, '#153B57', true);
text(item, '92 tests passed locally / lint and type checks passed in CI',
  80, 559, 1120, 90, 28);

item = slide('Questions and discussion',
  'Sources: report/report.md and supplied ownership rules. Suggested answers: the CLI null cache prevents persistent storage construction under --no-cache; fake Researcher isolates the CLI contract; team release still needs authored report sections, contribution statements, slides and PR approval. Final tag and Moodle upload are deferred. AI disclosure: Codex assisted Bailar-owned code, documentation and these slides.');
text(item, 'How does --no-cache avoid database access?\nWhy do CLI tests replace Researcher with a fake?\nWhat remains before the team release?',
  80, 245, 1120, 225, 34);
text(item, 'Bailar / CLI, deployment and assembly', 80, 560, 1120, 60, 28, '#087E8B');

const draft = path.join(BUILD_DIR, 'candidate.pptx');
await (await PresentationFile.exportPptx(deck)).save(draft);
const finalPath = path.join(BUILD_DIR, 'final', 'bailar.pptx');
await fs.mkdir(path.dirname(finalPath), { recursive: true });
await finalizePresentation({
  workspaceDir: path.dirname(BUILD_DIR), candidatePath: draft, finalPath,
  pythonExecutable: RUNTIME_PYTHON, explicitTotalSlideCount: 4,
  integrityValidatorPath: path.join(SKILL_DIR, 'container_tools/inspect_presentation_package_integrity.py'),
  layoutValidatorPath: path.join(SKILL_DIR, 'container_tools/inspect_presentation_layout_geometry.py'),
  layoutArgs: ['--expected-slide-size-emu', '12192000,6858000', '--validate-heading-fit'],
  fontPolicy: { basis: 'design', families: ['Arial'] },
  verifyArtifactToolImport: true, receiptPath: path.join(BUILD_DIR, 'validation.json'),
});
for (let i = 0; i < deck.slides.items.length; i++) {
  const png = await deck.export({ slide: deck.slides.items[i], format: 'png', scale: 1 });
  await fs.writeFile(path.join(BUILD_DIR, `slide-${i + 1}.png`),
    new Uint8Array(await png.arrayBuffer()));
}
console.log(finalPath);
