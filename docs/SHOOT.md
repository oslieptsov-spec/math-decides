# Recording checklist

The 90-second screencast and every screenshot in the README come from here.
Nothing on this list is about the recording software; it is about what ends up
in the frame.

## 1. Clean environment — before anything else

A screenshot leaks what a code sweep cannot see. `tools/sweep.py` reads the
working tree, the staged diff and the git history; it has never seen a browser
window, and it never will.

- [ ] Dedicated browser profile, or a private window. No tabs, no bookmarks
      bar, no extensions, no profile avatar.
- [ ] Terminal prompt shows no hostname, no username, no directory path that
      names anything. Use a bare prompt for the take.
- [ ] No notification banners. Do not disturb on.
- [ ] Nothing in the frame names an employer, a client, or an internal system.
- [ ] Desktop wallpaper and dock are out of frame or neutral.
- [ ] Recording is from the personal machine and the personal accounts used
      for the entry.

## 2. Before the take

- [ ] `make test` green.
- [ ] `python3 -m attacks --write` regenerated, table matches the suite.
- [ ] `python3 tools/record.py` refreshed the canned answer, the recorded
      rejection and the sabotage replay.
- [ ] Counter decided: `python3 tools/counter.py --reset <date> --reason "..."`
      if the published count should start from the launch date. The reset is
      recorded in the file either way; the page shows the date it counts from.
- [ ] Mode chip shows the path you intend to film.

## 3. The take — 90 seconds

| t | frame | what the viewer sees |
|---|-------|----------------------|
| 0:00 | landing, `incomplete-laws` already run | three panels; one output computed, three withheld |
| 0:10 | receipt panel, cursor on `defensive_factor` | dashed chip, `no declaration releases it` — the output no law can reach |
| 0:20 | explanation panel | the model restates the receipt; provenance line names model, build, path |
| 0:30 | switch preset to `declared-laws`, validate | **the money shot.** Amber chips travel to green and the values write themselves in; `defensive_factor` does not move. Hold the frame through the transition — roughly half a second — and do not cut on the click |
| 0:45 | attack console, one button per column | structure, schema, post-validator — three different reasons to say no |
| 0:55 | free-text field, type an override instruction, send | structural verdict, no prose, `receipt_sha unchanged` |
| 1:05 | `#rejected` | a real refused answer: repair, then `explanation unavailable — receipt stands` |
| 1:15 | `watch it fail without the guardrail` | recorded replay, watermark, silent releases |
| 1:25 | footer hash chain | `input_hash → receipt_sha → bound explanation` |

Deep links for deterministic takes: `#rejected`, `#sabotage`, and `?tour=N` for
any step of the guided walk. `?tour=0` skips state 0 and lands on the full
screen — that is the one to use for README stills.

The guided tour is this script made interactive, and it is staged rather than
dimmed: each step decides what exists on screen, so every frame is already a
clean shot with nothing else competing in it. Seven steps — the six scenes
above plus the assembly at the end, where the whole dashboard appears and the
viewer recognises every part of it.

If a scene changes here, change the card with it, or the video and the page
will start telling different stories.

## 4. After the take

- [ ] Watch the recording once at full size looking only at the edges of the
      frame, not at the content.
- [ ] Check the exported file's metadata for a username or machine name.
- [ ] Screenshots for the README taken headless from a clean profile, not from
      a working browser.
