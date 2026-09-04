# Recording the 60 second demo

## Before you hit record

Four things must be running. Check each one.

```bash
# 1. the tunnel, so Twilio can fetch the flood map
~/.local/bin/cloudflared tunnel --url http://127.0.0.1:5000
#    copy the https://<name>.trycloudflare.com line into .env as PUBLIC_BASE_URL

# 2. the API (restart it after changing .env)
.venv/bin/python3 -m flask --app api.app run --port 5000 --no-reload

# 3. the board
cd board && npx next dev -p 3000

# 4. check the health line and that a card is fetchable through the tunnel
curl -s http://127.0.0.1:5000/api/health
curl -s -o /dev/null -w "%{http_code}\n" "$PUBLIC_BASE_URL/alertcards/"
```

Without the tunnel the WhatsApp message still sends but arrives with no image, and
Twilio returns error 63019. That is the one failure that will ruin the take.

Open two windows side by side: the board at `http://127.0.0.1:3000/gate`, and your
phone on screen or mirrored. Have `http://127.0.0.1:3000/agents` on a second tab.

## The screen to record

**`/gate`, the Approvals page.** It is the only screen that carries the whole story:
the trigger, the agent chain, the human checkpoint, and the delivery. Everything else
is supporting material.

## The 60 seconds

**0:00 to 0:08 — open on `/gate`, phone visible**

> "This is a glacial outburst warning system for the Bhotekoshi corridor in Nepal.
> Nobody is watching a screen. There is no button that starts a run."

**0:08 to 0:18 — press "Send RED to Timure", hold on the phone**

> "This is the card the system would send. Real terrain, the real river network, the
> modelled flood path along it, in Nepali and English, with the arrival estimate for
> that specific village."

The phone buzzes in about five seconds. Let it land on camera. Do not talk over it.

**0:18 to 0:32 — press "Full chain, agent picks tools", then switch to the `/agents` tab**

> "That was the channel. This is the actual agent. It picks its own tools, twenty four
> calls last run, and when the flood router had no case for ten point two million cubic
> metres it rounded down, failed again, then bracketed the answer between five and one
> and reported both as bounds. Nothing in the prompt tells it to do that."

**0:32 to 0:44 — back to `/gate`, scroll to the pending gate**

> "It reached ALERT and then it stopped. Anything above YELLOW needs a named district
> officer. Here is the score, what moved it, and where the decision flips."

**0:44 to 0:54 — press Approve**

> "One signature and it goes out in two tiers, institutions first, then residents, each
> with their own arrival time. Every send comes back with a delivery receipt."

Point at the released table with the Twilio SIDs.

**0:54 to 1:00 — close**

> "Below YELLOW it posts itself. Above it, it cannot move without a person. Cancelling
> an alert is automatic, because raising fear needs a human and removing it does not."

## If you have 90 seconds instead

Insert after 0:32, on `/analysis`:

> "And it does not just say what. It says why. Here is the attribution across candidate
> causes with the evidence split per node, and the margin between the top two."

## What to say if asked

**"Is the AI making up the numbers?"**
No. The model never computes anything. Sixteen Python tools compute; the model chooses
which to call and reads what comes back. Every number in a claim carries an evidence ref.

**"What happens when the AI is down?"**
Azure falls back to Groq, Groq falls back to a deterministic run with no model at all,
and that falls back to the last known good status with its age shown. We tested it by
invalidating live keys.

**"Why is it cloud blind if it uses satellites?"**
The optical scenes for the event are 79 percent cloud. That is exactly why detection
runs on radar, which sees through it. We show both scenes on `/imagery` rather than
hiding the bad one.

**"Is the alert real or a mock?"**
The card, the routing, the terrain, the population and the Twilio delivery are real.
The institutional contact numbers are not routable, and the drill button is labelled
REPLAY - TEST on the card itself.

## Page map

| Page | Shows | Use it for |
|---|---|---|
| `/` | Live corridor status per settlement | Opening shot |
| `/gate` | Trigger, human checkpoint, delivery | **The main recording** |
| `/agents` | Each agent's inputs, outputs, live trace | Proving autonomy |
| `/analysis` | Root cause attribution with evidence splits | Depth question |
| `/predict` | Bayesian hazard probability and indicators | Method question |
| `/imagery` | Before and after swipe, cloud problem | Honesty question |
| `/preparedness` | Exposure, lead times, isolation | Impact question |
| `/gov` | Risk engine dashboard, validation | Technical question |
| `/pipeline` | Dataset to decision walkthrough | Non-technical audience |
| `/trace` | Raw run traces | Anyone who wants receipts |
