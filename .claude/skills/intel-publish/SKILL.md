---
name: intel-publish
description: "Phase 4 of the intelligence brief pipeline. Syncs briefs to the frontend data directory, builds the Vite app, and optionally starts the dev server. Triggered by /intel-publish or as the final step of /workflow."
---

# Intel Publish — Sync + Build

**Invocation:** `/intel-publish`

Publish the latest brief to the frontend.

## Steps

### 1. Sync briefs to frontend

```bash
python scripts/sync_briefs.py
```

This copies all `briefs/CSE_Intel_Brief_*.json` files to `src/data/`, generates `src/data/index.ts`, and cleans up old data files.

### 2. Build the frontend

```bash
npm run build
```

Verify the build succeeds with no TypeScript errors.

### 3. Optionally start dev server

```bash
npm run dev
```

The brief is then viewable at http://localhost:5173

## Output Contract

- **Input:** `briefs/CSE_Intel_Brief_*.json`
- **Output:** Built frontend in `dist/`, dev server at localhost:5173
