# ENZ UCS Auto Rename

REAPER helper for renaming selected media items with a Chinese natural-language
description and an official UCS CatID prefix.

## Runtime Flow

1. Start or reopen the local UCS UI.
   - Windows packaged build: `start_ucs_service_windows.bat`
   - macOS development build: `start_ucs_service_macos.command`
   - If the service is already running, the launcher only opens the browser UI
     and does not start a duplicate backend.
2. Run `enz_UCS_Auto_Rename_Selected_Items.lua` in REAPER.
3. Select one or more media items.
4. Open `http://127.0.0.1:8000/ui` from the REAPER script or a browser, enter
   Chinese text there, generate candidates, choose one, edit FXName, and click
   `在 REAPER 重命名`.
5. The REAPER script polls the local service and renames the currently selected
   media items when it receives the browser task.
6. The REAPER window stays open after renaming so another item batch can be
   processed.

The browser UI, REAPER helper window, and stop scripts can all request backend
shutdown through `POST /api/v1/shutdown`. If the browser tab is closed by
accident, run the launcher again to reopen the existing backend UI.

## macOS Development Test

From this repository:

```sh
chmod +x ucs_tool/scripts/start_ucs_service_macos.command
./ucs_tool/scripts/start_ucs_service_macos.command
```

The launcher starts the service in the background and opens the browser UI.
Verify:

```sh
curl -sS http://127.0.0.1:8000/health
curl -sS http://127.0.0.1:8000/api/v1/model_status
curl -sS -H 'Content-Type: application/json; charset=utf-8' \
  --data-binary '{"description":"带一点回音的清脆玻璃破碎声"}' \
  http://127.0.0.1:8000/api/v1/parse_ucs
```

Then copy or load `scripts/enz_UCS_Auto_Rename_Selected_Items.lua` in macOS
REAPER, keep its small window open, click `打开网页`, and use the browser page as
the main UI.

To stop the backend without the browser UI:

```sh
./ucs_tool/scripts/stop_ucs_service_macos.command
```

`ENZ_UCS_Launcher.html` is a static helper page for checking whether the backend
is online and reopening or stopping the UI. It cannot start the backend by
itself because browsers cannot run local programs directly.

See `ROADMAP.md` for the v0.2 UX scope and v0.3 semantic matching plan.

## API

`POST http://127.0.0.1:8000/api/v1/parse_ucs`

```json
{
  "description": "带一点回音的清脆玻璃破碎声"
}
```

The service returns the official `ucs_prefix`, a generated `fx_name`, confidence,
and up to three UCS candidates. Candidate scoring combines:

- `rule_score`: exact UCS fields, Chinese translations, aliases, and direct
  synonym hits.
- `semantic_score`: the offline local semantic matcher, using weighted UCS
  category profiles and concept-level boosts. This is still rule/token based,
  not a neural model.
- `fts_score`: SQLite FTS5 BM25 retrieval over weighted tokens from input
  metadata (description/filename/fxname/keywords/etc.), used to make matching
  robust when words are reordered or interrupted (e.g. "金属刀摩擦").
- `embedding_score`: optional real semantic-model score from a local
  SentenceTransformers-compatible embedding model. It is `0` unless
  `ENZ_UCS_EMBEDDING_MODEL` is configured.

The final `score` is the combined ranking score; output prefixes are still
restricted to official UCS CatID values.

## Optional Real Semantic Model

The service can add a real embedding-model retrieval layer without changing the
REAPER script or browser UI. This is intentionally opt-in so the default tool
does not download models or require heavy dependencies.

The normal user path is the browser UI:

1. Start the backend with `./ucs_tool/scripts/start_ucs_service_macos.command`.
2. Open the browser UI.
3. In `语义模型`, click `安装语义模型`.
4. Wait for installation to finish. It creates `ucs_tool/.venv-ucs`, installs
   `sentence-transformers`, downloads the configured model, and writes
   `ucs_tool/config.json`.
5. Click `关闭后端`, then run the launcher again. The macOS launcher reads
   `config.json` and enables the model automatically.

The setup script creates `ucs_tool/.venv-ucs` so Homebrew Python's
externally-managed-environment restriction is not touched. For manual setup, it
can still be run directly:

```sh
./ucs_tool/scripts/setup_semantic_model_macos.command
```

The model must be available locally or resolvable by the installed
SentenceTransformers runtime. Check activation with:

```sh
curl -sS http://127.0.0.1:8000/api/v1/model_status
```

When enabled, each candidate shows `模型` in the browser score line. That score
comes from vector similarity between the Chinese prompt/context and each UCS
category profile.

For command-line comparison while tuning models:

```sh
python3 -B ucs_tool/backend/eval_semantic_model.py
python3 -B ucs_tool/backend/eval_semantic_model.py "坚硬的石头撞击地面" "金属刀摩擦"
```

## Data

`backend/data/ucs_v8_2_1_zh.json` is generated from `UCS v8.2.1 Full Translations.xlsx`
using `backend/build_ucs_data.py`. The official CatID in that JSON is the source
of truth; Chinese aliases only influence matching scores.
