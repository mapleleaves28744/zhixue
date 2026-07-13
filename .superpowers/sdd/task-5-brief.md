### Task 5: 完整验证与事实基线

**Files:**
- Modify: `docs/当前实现基线.md`

- [ ] **Step 1: Update baseline fact**

Add one factual Agent Runtime bullet: intent-scoped candidate tools, existing event/step timing, and atomic queued-task claim are implemented; no new database table or API is introduced.

- [ ] **Step 2: Run focused regression**

Run: `cd backend && python -m pytest tests/test_agent_runtime.py tests/test_supervisor_intents.py tests/test_agent_harness.py tests/test_agent_cancellation.py -v`

Expected: PASS.

- [ ] **Step 3: Run full verification**

Run: `cd backend && python -m pytest`

Expected: PASS. If unrelated dirty-worktree changes fail, report them without altering those files.

- [ ] **Step 4: Check docs and diff**

Run: `python scripts/check_docs.py && git diff --check`

Expected: exit code 0.

- [ ] **Step 5: Commit the verified baseline**

Commit: `git add docs/当前实现基线.md && git commit -m "docs: record agent runtime convergence"`
