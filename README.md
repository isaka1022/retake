# Retake

An AI film crew that plans, shoots, edits and reviews a short documentary — and
sends its own work back for a retake when it is not good enough.

You give it one line. It picks locations, writes the narration, records the
voice, clears the image rights, shoots every cut, assembles the reel, watches
what it made, and only then asks a human whether to publish.

```
"水と滝の聖地を30秒で"  →  a 25-second graded, captioned, narrated film
```

## What it does on its own

- **Chooses what to shoot.** The producer picks three or four locations from a
  catalogue of twenty and writes the narration for each.
- **Decides how to shoot it.** The storyboard assigns a camera move to every
  cut and picks the medium — a Ken Burns move across a photograph, or a shot
  generated from that same photograph with Veo.
- **Clears the rights.** CC0, CC BY and CC BY-SA do not impose the same
  obligations. The credit is decided per still, and share-alike on any one of
  them binds the finished film.
- **Times the picture to the read.** The narration is recorded first, because
  reading speed runs near 4.5 characters a second against the storyboard's
  guess of six.
- **Criticises its own work.** The director watches the assembled reel as
  video, scores it, and issues notes carrying the replacement camera move,
  exposure and length.
- **Stops before it publishes.** Releasing is not reversible, so a person
  watches the reel and decides. If the director never signed off, the objection
  is put in front of them.

## Requirements met

| Requirement | How |
|---|---|
| Gemini 3.5 or later | `gemini-3.5-flash` for planning, storyboarding and multimodal review |
| Google agent framework | ADK 2.0 graph workflow (`google-adk` 2.8.0) |
| Google Cloud infrastructure | Cloud Run (service + hosted UI), Cloud Storage, Secret Manager |
| Bonus models | Veo 3.1 Fast (image-to-video), Gemini TTS for narration |

## Run it locally

Python 3.10+ and `ffmpeg` on your PATH.

```bash
git clone <this repo> && cd retake
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export GOOGLE_API_KEY=...          # https://aistudio.google.com/apikey

# Build the location catalogue (spots, images, licence metadata)
PYTHONPATH=. python scripts/build_catalog.py

# One film, start to finish
PYTHONPATH=. python scripts/run_local.py "水と滝の聖地を30秒で"

# The same run, stopping at the screening gate for a human decision
PYTHONPATH=. python scripts/test_hitl.py "水と滝の聖地を30秒で" publish
```

The finished reel lands in `out/published/<run>/`.

To drive it through the ADK web UI instead:

```bash
adk web .
```

## Deploy to Cloud Run

`adk deploy cloud_run` generates an image without `ffmpeg` and strips the dev
server, so this repo ships its own `Dockerfile` and `main.py`.

```bash
zsh scripts/gcp_prep.sh      # bucket, secret, IAM — reads GOOGLE_API_KEY from the env
zsh scripts/deploy.sh        # Cloud Build → Cloud Run
```

`gcp_prep.sh` pipes the key into Secret Manager over stdin so the value never
reaches a command line or a shell history. `deploy.sh` injects it with
`--set-secrets`.

## Architecture

See [docs/architecture.md](docs/architecture.md) for the graph, the reasoning
behind its shape, and how state and failure are handled.

```
retake/agent.py     the call sheet — who works when, who waits on whom
retake/nodes/       the crew. Read and write graph state, decide routes
retake/services/    generation, rendering and licence logic. Knows nothing of ADK
```

The split is deliberate: `services/` can be exercised without the graph, so a
rendering or model problem can be isolated from an orchestration one.

## Data

Twenty locations drawn from a personal power-spot dataset, paired with
Wikimedia Commons photographs and their licence metadata. Every still in the
catalogue carries an artist and a licence; the rights node refuses any that
does not.

## Costs

Veo bills per generated second, so generation is limited to one cut per film
and cached by source image and prompt — a retake of a generated shot regrades
it rather than paying to make it again.

## Pre-existing work disclosed

Written during the submission period. Two things carried in:

- The ffmpeg recipes (Ken Burns easing, oversampling to avoid zoompan jitter)
  come from the author's own earlier video tooling.
- The location dataset (`spots.json`) predates the hackathon; the catalogue
  builder that joins it to Wikimedia licence metadata is new.

The budget-guard and confidence-cascade patterns in `services/` are
reimplementations of ideas from the author's own `llm-lane` package, not copied
code.
