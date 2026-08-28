# 4-minute demo script

**Requirements**: live, unedited, about 4 minutes, includes visible proof it runs on GCP.

**Measured baseline** (Cloud Run, revision 00004, 3 cuts, 1 Veo cut, 1 retake):
**172 seconds** from submitting the brief to stopping at screening. Breakdown:
producer 5s → narration 8s → shoot take 1 83s (including Veo generation) →
edit 14s → director 9s → shoot take 2 33s → edit 15s → director 5s.

**Design**: talk while it's running. Don't fill the wait with explanation —
make sure **what's being explained is what's on screen** at that moment.

| Time | Screen | Talk track | Judging criterion targeted |
|---|---|---|---|
| 0:00–0:25 | A finished video or a folder of raw footage | How many hours one music video takes — planning, shooting, editing, rights clearance, all done solo | Innovation |
| **0:25** | Typing the brief into the ADK Web UI | **This is where it goes live. Everything after this is really running** | — |
| 0:25–1:00 | Trace view (producer → storyboard → rights check → narration) | The nine-member crew and the graph structure. Rights check detects CC BY-SA and it decides the film's licence | Architecture |
| 1:00–2:00 | The camera node running | Narration length sets shot length, not the other way round. Storyboard picks stills vs. Veo per cut. **Veo is rendering right now** | Innovation / bonus |
| 2:00–2:30 | Editor → director | The director watches the **actual assembled video** on Gemini and scores it. This is where the score lands | Innovation |
| **2:30–3:10** | **RETAKE fires and it goes back to the camera** | The centerpiece. Read out exactly what the director flagged. It remembers its previous notes and checks whether they were addressed | **Innovation 40%** |
| 3:10–3:25 | Stopped at screening | Publishing can't be undone, so a person decides. If the director never signed off, its objection is shown here | Architecture 30% |
| 3:25–3:40 | Approved → goes live on YouTube | Show the licence credit in the description | Innovation (real-world side effect) |
| 3:40–4:00 | Cloud Run console / GCS bucket | Both `reel_t1` and `reel_t2` exist — proof the retake actually produced a different version | **Visible proof it runs on Google Cloud** |

## Confirmed on the deployed UI (live run, 2026-08-27)

Ran the whole path on the deployed Web UI. Here's what's actually available to show in production.

| Screen | What it shows |
|---|---|
| Events pane | Each crew member's output streams by in readable form — the producer's title, theme, cut list |
| Info pane | The **node path** (`retake@1/producer@1`) and the state diff |
| Event list | `State: clearances, blocked_shots, work_licence` (rights check), `State: cuts, budget, failed_cuts` (camera), etc. — **who changed what** |
| Branches | **`route: RETAKE`** and **`route: OK`** appear as buttons — you can watch the graph branch live |
| Artifacts tab | `preview.mp4` as a **playable video**. The version number climbs with every take |
| Screening | The `adk_request_input` form: the director's score and licence text, a `decision` field, and Submit |

`decision` is **free text**, not a dropdown enum. Type `publish`. `retake`
sends it back to the camera; `abandon` withdraws it from publication.

**The beats land in the same order the UI shows them**, so it's possible to
narrate straight down the screen as it scrolls.

## To confirm in rehearsal

- [ ] Does the run land at the screening gate within 3 minutes of submitting the brief (Veo generation varies 39–49s)?
- [ ] Does a retake **fire at least once**? (Measured: 5 for 5. "Introduce sacred sites of water and waterfalls in 30 seconds" went 75 → 92; "Sacred mountain-worship sites in 30 seconds" went to take 3 — both were sent back at least once.)
- [ ] Does the YouTube upload succeed? (Requires `scripts/youtube_login.sh` already run.)
- [ ] Is the trace view legible over screen share?

## Where to cut if running long

1. Trim the 0:00–0:25 intro to 15 seconds.
2. Drop the brief to two cuts (shoot take 1 comes in about 20 seconds shorter).
3. Show the Cloud Run console in the background while it's running, not at the end.

## Never cut

- The moment a retake fires (the Innovation 40% centerpiece)
- The moment a person approves at screening (the Architecture 30% core)
- The screen proving it's running on GCP (required for submission)
