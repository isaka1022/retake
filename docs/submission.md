# Devpost submission text

## Inspiration

I make music and short films on my own. The part that takes longest is not any
single craft — it is being every craft in sequence. Plan, shoot, cut, watch it
back, decide it is not good enough, do it again. The watching-it-back and
deciding is the part nobody automates, because it is the part that requires
taste.

So I built the crew instead of the tool: a director who watches the cut and
sends it back.

## What it does

You give it one line — "a 30-second film about the sacred waterfalls" — and a
crew of nine takes it from there.

The producer picks locations and writes the narration. The storyboard assigns a
camera move to each cut and decides which shots are worth generating with Veo
rather than panning across a photograph. The rights agent reads the licence on
every still and works out what the finished film inherits. The narrator records
the read, and the picture is timed to it. The camera shoots. The editor cuts,
levels the audio and makes a viewing proxy.

Then the director watches the reel — as video, through Gemini — scores it, and
either signs off or sends specific shots back with a replacement camera move
and exposure.

Only after that does a person get asked. Publishing is not reversible, so the
run stops at a screening gate with the reel and the director's verdict. If the
director never signed off, the objection is shown too.

## How I built it

An ADK 2.0 graph workflow on Cloud Run. Each crew member is a node; the graph
is the call sheet. The retake is a real cycle in the graph, and the screening
is a genuine pause — the run stops and waits for a human.

- **Gemini 3.5 Flash** — planning, storyboarding, and watching the finished
  reel to review it
- **Veo 3.1 Fast** — image-to-video from the same still the rest of the reel
  uses, so the shot keeps the real location
- **Gemini TTS** — the narration
- **Cloud Run** — the service and its UI
- **Cloud SQL** — sessions, so a restart does not drop a reel waiting at the
  screening gate
- **Cloud Storage** — masters
- **Secret Manager** — credentials
- **ffmpeg** — Ken Burns with eased motion, captions in Japanese, loudness

## Data

Twenty locations from a power-spot dataset I had already collected, paired with
Wikimedia Commons photographs and their licence metadata. The catalogue keeps
the artist and licence for every image, and the rights node refuses anything
missing them.

## Challenges

**A critic with no memory never converges.** The first director re-judged the
reel from scratch every take. Scores went 68, 62, 68 — it just kept finding new
complaints. Giving it its own previous notes, and asking whether they had been
addressed, changed the run to 78 then 96.

**A critic can only ask for what the crew can do.** The director kept demanding
the blown highlights be fixed while the camera's only controls were framing and
length. The note was correct and unactionable, so the loop spun. Adding an
exposure control was what actually ended it.

**"Out of takes" is not "approved."** The first version relabelled a reel as
accepted once it hit the take limit, while the director's own comment called it
unacceptable. Now it goes to the screening marked unapproved, with the
objection attached, and the person decides.

**Silent fallbacks look exactly like success.** Loudness normalisation parsed
ffmpeg's report as JSON and failed on the trailing log lines, so every run
quietly copied the file instead. The measurement was printing correctly the
whole time.

**Cloud Run rejects a buffered response over 32MB.** The app returned 200 and
the frontend still turned it into a 500. Masters are streamed now.

## What's next

The crew currently shoots from a library of photographs. The obvious next step
is pointing it at my own footage — the same director, the same screening gate,
real material.
