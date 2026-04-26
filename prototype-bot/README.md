# Vera Prototype Candidate Bot

This is a dependency-free prototype bot for exercising the challenge judge.
It is intentionally deterministic and rule-based so scoring behavior is easy
to inspect.

## Run

```bash
MAGICPIN_JUDGE_TOKEN=local_dev_token python3 prototype_bot.py \
  --port 8080 \
  --preload-dir /tmp/magicpin-expanded-check
```

Open the browser UI at:

```text
http://127.0.0.1:8080/
```

## Optional Gemini Backend

If you want the composer to use Gemini instead of the deterministic fallback,
set `GEMINI_API_KEY`:

```bash
MAGICPIN_JUDGE_TOKEN=local_dev_token \
GEMINI_API_KEY="your_key_here" \
python3 prototype_bot.py --port 8080 --preload-dir /tmp/magicpin-expanded-check
```

If Gemini fails or the key is not present, the bot falls back to the local
rule-based composer.

## Render Deployment

This repo includes a root `render.yaml` blueprint. In Render:

1. Create a new Blueprint from the GitHub repo.
2. Render will run:
   ```bash
   cd prototype-bot && python3 challenge/dataset/generate_dataset.py --seed-dir challenge/dataset --out expanded
   ```
3. Render will start:
   ```bash
   cd prototype-bot && python3 prototype_bot.py --host 0.0.0.0 --port $PORT --preload-dir expanded
   ```
4. Add `GEMINI_API_KEY` as a secret environment variable if you want Gemini composition.
5. Use the Render URL as the candidate bot URL.

The browser UI is available at `/`; judge endpoints are available at `/v1/*`.

## Smoke Test

Generate the expanded dataset first if needed:

```bash
python3 ~/Downloads/magicpin-ai-internship-challenge/dataset/generate_dataset.py \
  --seed-dir ~/Downloads/magicpin-ai-internship-challenge/dataset \
  --out /tmp/magicpin-expanded-check
```

Then, in another terminal:

```bash
python3 run_smoke_test.py --url http://127.0.0.1:8080
```

## Implemented Contract

- `GET /v1/healthz`
- `GET /v1/metadata`
- `POST /v1/context`
- `POST /v1/tick`
- `POST /v1/reply`
- Optional `POST /v1/teardown`

The bot stores context in memory, dedupes by suppression key, composes
messages from category/merchant/trigger/customer context, and handles common
reply classes:

- auto-reply
- explicit yes / go-ahead intent
- opt-out / not interested
- hostile or off-topic
- ambiguous replies
