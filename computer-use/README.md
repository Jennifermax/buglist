# Computer Use Test Platform Skeleton

This repository contains a minimal platform skeleton for running software UI test cases with:

- `computer use` for actions such as opening pages, waiting, and clicking
- `vision AI` for visual assertions such as modal, logo, QR code, and image presence
- `OCR` for text extraction and text-based assertions
- a unified runner that returns per-step results and a final `pass` or `fail`

## Why split the engines

- `computer use` is good at operating the page
- `vision` is good at checking whether a visual element exists
- `OCR` is good at extracting text for precise assertions

Keeping them separate makes the platform more stable and easier to evolve.

## Protocol shape

Each test case contains:

- `meta`: case metadata
- `runtime`: execution options
- `steps`: ordered action and assertion steps
- `mock_context`: optional development fixture used by the local mock runner

## Run the sample case

```bash
python3 run_case.py cases/TC154.share-popup.json
```

The current implementation uses mock backends so the flow can run end to end in this empty workspace. To move to production, replace the backends in [backends.py](/Users/corn/project/own/buglist/computer-use/src/computer_use_platform/backends.py).

## Run a real browser execution

```bash
python3 run_live_case.py cases/TC154.original.json
```

This path executes the original case format against the real webpage with Playwright and returns a program-generated `pass` or `fail`.

The live runner now supports two modes:

- `AI mode`: if `COMPUTER_USE_AI_API_KEY` or `OPENAI_API_KEY` is configured, screenshot assertions are sent to an OpenAI-compatible vision model
- `fallback mode`: if AI is not configured, the runner falls back to deterministic local rules

## Configure AI

Copy [.env.example](/Users/corn/project/own/buglist/computer-use/.env.example) to `.env` and fill in the values:

```bash
cp .env.example .env
```

Then set at least:

- `COMPUTER_USE_AI_API_KEY`
- `COMPUTER_USE_AI_MODEL`

Optional:

- `COMPUTER_USE_AI_BASE_URL`
- `COMPUTER_USE_AI_TIMEOUT`
- `COMPUTER_USE_HEADLESS`

## Save Login State

Run this command to open a real browser for manual login:

```bash
python3 capture_login_state.py
```

After you finish logging in, press Enter in the terminal. The session state will be saved to:

- `auth/storage_state.json`

The live runner will automatically reuse this login state on the next run.

## Execution artifacts

Every live run writes:

- screenshots into `artifacts/`
- the final machine-generated result into `artifacts/<case_id>-result.json`

## Suggested production architecture

1. `computer_use` backend
   Open the browser, navigate, click, scroll, and capture screenshots.
2. `vision` backend
   Detect modal, logo, poster image, QR code, and background regions from screenshots.
3. `ocr` backend
   Extract text from the modal or from cropped regions for precise assertions.
4. `runner`
   Execute steps, collect evidence, and aggregate the final result.

## Next integration points

- Replace `MockComputerUseBackend` with a real browser controller
- Replace `MockVisionBackend` with a screenshot + VLM detector
- Replace `MockOCRBackend` with a real OCR engine
- Save screenshots and intermediate evidence for failed steps
- Add retry logic and fallback strategies for ambiguous clicks
