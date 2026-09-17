# Bailar's presentation contribution

`bailar.pptx` contains four editable slides: title, CLI, Docker/CI and Q&A.
`bailar.pdf` is the matching handout. The deck uses English to match the repository.
Insert the other three members' six authored slides before Q&A during assembly.
Those slides were not supplied for this revision.

Source notes identify the relevant repository files, verification limits and AI
assistance. Docker and CI passed for the head f090268 in Actions run 35284135541.

`build_slides.mjs` uses the Codex bundled `@oai/artifact-tool` runtime. Set
RUNTIME_NODE_MODULES, SKILL_DIR (the Presentations skill), RUNTIME_PYTHON and
BUILD_DIR to absolute paths, then run it with the bundled Node executable.
Use a fresh BUILD_DIR for each build because the finalizer does not overwrite.
The companion export_pdf.py uses reportlab and the four rendered slide PNGs.

The local finalizer could not spawn Python (EPERM). Its package and layout
validators were therefore executed directly: four slides, approved Arial font,
correct 16:9 dimensions, zero findings. Artifact Tool re-imported the PPTX and
rendered every slide for visual review. No native PowerPoint check is claimed.
