# Task 2 Report — Split Agent Runtime ToolSets

## Scope completed

- Moved the 24 nested `build_learning_tool_registry()` handlers into five focused ToolSet modules:
  - `knowledge_tools.py`
  - `learning_tools.py`
  - `profile_tools.py`
  - `review_tools.py`
  - `media_tools.py`
- Added `toolsets/common.py` for the shared `register_tool(...)` implementation and package exports in `toolsets/__init__.py`.
- Kept `build_learning_tool_registry(db, current_user, *, result_loader=None, result_saver=None)` as the synchronous public factory.
- Preserved the established registration sequence by invoking ToolSet registrations in the original 24-tool order, including the high-risk confirmation metadata for `apply_evolution_strategy`.
- Added a Registry contract test covering the complete public name set, courseware required field, evolution risk/confirmation boundary, and all public ToolSet registration exports.
- Updated the pre-existing source-location assertion for explanation resource references to inspect its new ToolSet module.

## TDD record

1. Added `test_learning_registry_keeps_public_tool_contracts` before production ToolSet code.
2. The requested test command could not start because the shell has no `python` executable. Re-ran it with the project interpreter:
   `backend/.venv/bin/python -m pytest tests/test_agent_runtime.py::test_learning_registry_keeps_public_tool_contracts -v`.
3. RED result: expected `ModuleNotFoundError: No module named 'app.agent_runtime.toolsets'`.
4. Added the ToolSet modules and thin compatibility factory.
5. GREEN result: Registry contract test passed.

## Verification

- `backend/.venv/bin/python -m pytest tests/test_agent_runtime.py tests/test_tool_registry_jsonschema.py -v`
  - 47 passed.
- `backend/.venv/bin/python -m pytest tests/test_audio_provider.py tests/test_multimodal_review.py -v`
  - 9 passed.
- `git diff --check`
  - passed.

## Scope exclusions

- Did not modify `structured_outputs.py`, `prompt_service.py`, real-provider acceptance files, plans/specifications, API, schema, model, migration, or unrelated worktree changes.
- No database or API changes.
