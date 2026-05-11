# ENZ UCS Auto Rename Roadmap

## v0.2 - Browser-Controlled Rename UX

- Keep one persistent ReaImGui window open until the user closes it.
- Use a local browser page for Chinese description input, candidate choice, and
  FXName editing because ReaImGui text input is unreliable for Chinese IME in
  the tested macOS setup.
- Keep the REAPER ReaImGui window as a lightweight task runner that reports
  selected item count and executes rename tasks sent from the browser.
- Keep the window open after renaming so the user can select another item batch
  and continue.
- Show REAPER connection state, selected item count, candidate choice, editable
  FXName, and generated base name in the browser.
- Keep a debug log for service and parsing failures.

## v0.3 - Semantic Matching And App Lifecycle

### App Lifecycle

- Add idempotent macOS and Windows launchers: if the backend is already
  running, reopen the browser UI instead of starting a duplicate service.
- Start the backend in the background from the launchers so the terminal window
  does not need to remain open.
- Add browser-side, REAPER-side, and standalone stop controls that call the
  backend shutdown endpoint.
- Provide a static HTML launcher/status page that can reopen or stop an already
  running backend and explains why pure HTML cannot start local programs.

### Semantic Matching

- Keep official UCS CatID values as the only valid category output. (Done)
- Add a semantic layer for classification using a local offline matcher built
  from weighted UCS category profiles, character n-grams, English tokens, alias
  terms, and concept-level boosts. (Done)
- Use rules and aliases as stable score boosters while allowing semantic scores
  to add candidates and rerank weak exact matches. (Done)
- Improve FXName generation by excluding generic selected-category words such
  as MAGIC/法术 from the generated FXName. (Done)
- Return transparent evidence for each candidate: confidence, matched words,
  semantic score, and rule score. (Done)

### Semantic Model Preview

- Add an optional SentenceTransformers-compatible embedding layer that can rank
  UCS category profiles by vector similarity when `ENZ_UCS_EMBEDDING_MODEL` is
  configured. (Done)
- Keep the embedding model opt-in so the default package remains lightweight and
  offline-rule matching still works without extra Python dependencies. (Done)
- Expose model activation and load errors through `/api/v1/model_status`. (Done)
- Add a small evaluation set of Chinese natural-language prompts and expected
  UCS CatIDs before tuning more weights.
