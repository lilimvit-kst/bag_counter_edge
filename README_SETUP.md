# OpenSpec baseline setup for Bag Counter Edge

This directory is a brownfield baseline generated from the current repository implementation.

## Install OpenSpec

```bash
npm install -g @fission-ai/openspec@latest
openspec --version
```

## Add this baseline

Copy the entire `openspec/` directory into the repository root and commit it.

If OpenSpec has not yet been initialized for your coding assistant, run from the repository root:

```bash
openspec init
```

Select the AI coding tool(s) you actually use. Current OpenSpec preserves existing specs/changes when refreshing an existing `openspec/` directory, but review the init output before committing generated tool-integration files.

Then validate:

```bash
openspec validate --all --strict
```

## Recommended first workflow

Start by exploring the counting contract before changing the model:

```text
/opsx:explore counting correctness, tracker/handover coupling, and current test gaps
```

Then create the first change:

```text
/opsx:propose add deterministic counting-contract tests for tripwire, handover, and exactly-once BagEvent persistence without changing production behavior
```

The exact slash-command spelling can differ by coding tool; `openspec init` prints the correct invocation for the selected tool.

## Important

Read `BASELINE_AUDIT.md` before proposing a model/tracker migration. It records current code/documentation mismatches that were intentionally not turned into normative baseline requirements.
