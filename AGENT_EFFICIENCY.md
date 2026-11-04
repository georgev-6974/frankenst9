# Working efficiently in a long session (guide for coding agents)

Goal: keep each message cheap so one chat lasts for hundreds of turns. Written from one long, successful project; adapt to your tool.

## 1. Know your tool's context handling
- Long chats get **compacted**: older turns are replaced by a written summary. In Claude Code this happens automatically when the context fills, or by hand with `/compact` (optionally with focus text, e.g. `/compact keep the file list and open TODOs`). Other tools call it "summarize", "condense" or "new chat from summary".
- If your tool has none of these, tell the user when the chat gets long and offer a **handoff note** (see 6) so they can start a fresh chat without losing anything.
- Every message re-sends the whole context. Smaller context = cheaper every turn. Most savings come from not letting it fill with junk.

## 2. Don't put big things in the context
- Never print whole files "to check". Search first (`grep -n`), then read only the lines you need (`sed -n 120,160p`, or a Read with offset/limit).
- Never re-read a file you just edited. The edit tool errors if it failed.
- Cap noisy output: `| tail -20`, `| head -50`, `--quiet` flags. Build logs: show only errors.
- Don't paste long tool output back into your reply.

## 3. Edit small, edit exact
- Use targeted edits (replace one block) or a short script (`python3 - <<'E' ... E`) that applies several edits at once. Don't rewrite or re-send a whole file for a 3-line change.
- Batch independent edits and independent reads into one turn (parallel tool calls) instead of one call per turn.
- After scripted edits run a cheap check (a lint/syntax script) instead of a full build when a build is slow or not available.

## 4. Talk less
- Say what changed in 2-5 lines. No recap of steps, no restating the request, no long lists of "what I did".
- Ask a question only when a wrong guess is expensive. Otherwise pick the sensible default, say which in one line, and go.
- Follow the user's standing rules (tone, format, naming) without being reminded; keep them in the handoff note.

## 5. Keep a map instead of re-discovering
- Keep a short project notes file (architecture, where things live, conventions, gotchas). Read it at the start of a session; append a few lines after each delivery.
- Use small helper scripts for repeated chores (build, zip, check) so the commands stay one short line.

## 6. Handoff note (also what a good compaction summary contains)
1. Goal and the user's standing instructions (verbatim where it matters).
2. What is done, what is half-done, what is next.
3. File map: path -> one-line purpose, only for files that matter.
4. Decisions and the reasons (so they are not re-argued).
5. Known bugs/risks and what the user reported.
6. Exact commands (build, package, deliver).
Keep it under ~1 page. Facts, not narrative.

## 7. Be honest about what you didn't verify
State plainly when something is untested or uncompiled. It saves a round trip when the user hits the error, and keeps trust.
