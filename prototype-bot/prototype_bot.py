#!/usr/bin/env python3
"""Dependency-free prototype candidate bot for the magicpin AI challenge.

Run:
  MAGICPIN_JUDGE_TOKEN=local_dev_token python3 prototype_bot.py --port 8080
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib import error, request
from urllib.parse import urlparse


START = time.time()
TOKEN = os.environ.get("MAGICPIN_JUDGE_TOKEN", "local_dev_token")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
PUBLIC_URL = os.environ.get("PUBLIC_URL", "http://localhost:8080")
LAST_GEMINI_STATUS = {"ok": False, "error": None}

contexts: dict[tuple[str, str], dict[str, Any]] = {}
conversations: dict[str, list[dict[str, Any]]] = {}
sent_bodies: dict[str, set[str]] = {}
used_suppression_keys: set[str] = set()


INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Vera Prototype Bot</title>
  <style>
    :root{--green:#173f2f;--accent:#2d6a4f;--paper:#f7f5f0;--line:#e6e1d8;--muted:#66645f}
    body{font-family:Inter,system-ui,sans-serif;margin:0;background:var(--paper);color:#171717}
    main{max-width:1040px;margin:0 auto;padding:34px 18px}
    h1{font-size:42px;line-height:1;margin:0 0 12px}
    h2{font-size:28px;margin:0 0 14px}
    p{color:var(--muted);line-height:1.6}
    button,select,input,textarea{font:inherit}
    .card{background:#fff;border:1px solid var(--line);border-radius:10px;padding:22px;margin:16px 0}
    .row{display:flex;gap:12px;flex-wrap:wrap;align-items:center}
    .row>*{min-height:44px}
    button{background:var(--accent);color:#fff;border:0;border-radius:8px;padding:10px 15px;font-weight:800;cursor:pointer}
    button.secondary{background:#edf3ef;color:var(--green);border:1px solid #c9ded5}
    button.chip{background:#fff;color:var(--green);border:1px solid #cfc9bd;font-weight:750}
    select,input,textarea{border:1px solid #d0ccc4;border-radius:8px;padding:10px;background:white}
    select{min-width:min(100%,560px);flex:1}
    input{min-width:min(100%,340px)}
    textarea{width:100%;min-height:168px;box-sizing:border-box;line-height:1.45}
    pre{white-space:pre-wrap;background:#102b21;color:#fff;border-radius:8px;padding:14px;overflow:auto}
    .muted{font-size:13px;color:var(--muted)}
    .clean{background:#e8f0ee;border:1px solid #c9ded5;border-radius:8px;padding:18px;margin:10px 0 18px;color:#173f2f;font-size:21px;line-height:1.45;font-weight:720}
    .label{font-size:12px;font-weight:900;color:var(--accent);text-transform:uppercase;letter-spacing:.04em;margin-top:18px;margin-bottom:8px}
    .conversation{display:grid;grid-template-columns:1fr;gap:10px}
    .bubble{border-radius:10px;padding:14px 16px;line-height:1.45;max-width:850px}
    .bot{background:#e8f0ee;color:#173f2f;border:1px solid #c9ded5}
    .merchant{background:#f8f6f1;color:#1d1d1d;border:1px solid #e4ded3;justify-self:end}
    details{margin-top:12px}
    summary{cursor:pointer;color:var(--accent);font-weight:900}
    code{background:#f2eee6;border-radius:4px;padding:1px 5px}
    .two{display:grid;grid-template-columns:1fr 1fr;gap:16px}
    @media(max-width:760px){h1{font-size:34px}.two{grid-template-columns:1fr}.clean{font-size:18px}}
  </style>
</head>
<body>
  <main>
    <h1>Vera Prototype Bot</h1>
    <p>This URL exposes the same HTTP contract candidates will implement, plus a cleaner demo surface for judging message quality. Pick a scenario, generate the assistant's first message, send a merchant reply, then copy the transcript into the judging chat.</p>
    <div class="card">
      <h2>1. Pick a scenario</h2>
      <div class="row">
        <select id="trigger"></select>
        <button onclick="tick()">Generate bot message</button>
      </div>
      <div class="label">Assistant message</div>
      <div id="tickClean" class="clean">Pick a scenario and generate a bot message.</div>
      <details>
        <summary>Raw /v1/tick JSON</summary>
        <pre id="tickOut">Loading triggers...</pre>
      </details>
    </div>
    <div class="card">
      <h2>2. Send a merchant reply</h2>
      <p class="muted">Use one of the examples or type your own reply. The conversation ID is filled automatically from the generated message.</p>
      <div class="row" style="margin-bottom:12px">
        <button class="chip" onclick="setMerchantReply('Yes please send it')">Interested</button>
        <button class="chip" onclick="setMerchantReply('Thank you for contacting us. We will get back to you soon.')">Auto-reply</button>
        <button class="chip" onclick="setMerchantReply('How much will this cost?')">Pricing ask</button>
        <button class="chip" onclick="setMerchantReply('Can you also help me file GST?')">Off-topic</button>
        <button class="chip" onclick="setMerchantReply('Not interested')">Decline</button>
      </div>
      <div class="row">
        <input id="conv" placeholder="conversation ID will appear here" readonly />
        <input id="msg" placeholder="merchant reply" value="Yes please send it" />
        <button onclick="reply()">Send merchant reply</button>
      </div>
      <div class="label">Assistant reply</div>
      <div id="replyClean" class="clean">Generate a bot message first, then send a merchant reply.</div>
      <details>
        <summary>Raw /v1/reply JSON</summary>
        <pre id="replyOut"></pre>
      </details>
    </div>
    <div class="card">
      <h2>3. Copy judge transcript</h2>
      <p class="muted">Paste this into the judging chat to score decision quality, engagement, compulsion, adaptation, and constraint discipline.</p>
      <textarea id="transcript" readonly>Generate a bot message to build the transcript.</textarea>
      <div class="row" style="margin-top:12px">
        <button onclick="copyTranscript()">Copy transcript</button>
        <button class="secondary" onclick="resetDemo()">Reset page</button>
      </div>
    </div>
    <div class="card">
      <h2>Contract endpoints</h2>
      <pre>GET  /v1/healthz
GET  /v1/metadata
POST /v1/context
POST /v1/tick
POST /v1/reply</pre>
    </div>
  </main>
  <script>
    let lastAction = null;
    let lastReply = null;
    let triggerMap = {};

    function escapeHtml(value){
      return String(value || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    }
    function triggerLabel(t){
      const merchant = t.merchant_id ? t.merchant_id.replace(/^m_\\d+_/, '').replaceAll('_', ' ') : 'unknown merchant';
      return `${t.id} | ${t.kind || 'trigger'} | ${merchant}`;
    }
    async function loadTriggers(){
      const res = await fetch('/demo/triggers');
      const data = await res.json();
      const select = document.getElementById('trigger');
      triggerMap = Object.fromEntries(data.triggers.map(t => [t.id, t]));
      select.innerHTML = data.triggers.map(t => `<option value="${escapeHtml(t.id)}">${escapeHtml(triggerLabel(t))}</option>`).join('');
      document.getElementById('tickOut').textContent = JSON.stringify(data, null, 2);
      updateTranscript();
    }
    async function tick(){
      const id = document.getElementById('trigger').value;
      lastAction = null;
      lastReply = null;
      document.getElementById('replyOut').textContent = '';
      document.getElementById('replyClean').textContent = 'Now send a merchant reply.';
      const res = await fetch('/demo/tick', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({available_triggers:[id], force:true})});
      const data = await res.json();
      document.getElementById('tickOut').textContent = JSON.stringify(data, null, 2);
      if(data.actions && data.actions[0]) {
        lastAction = data.actions[0];
        document.getElementById('conv').value = lastAction.conversation_id;
        document.getElementById('tickClean').textContent = lastAction.body;
      } else {
        document.getElementById('tickClean').textContent = 'No message sent for this trigger.';
        document.getElementById('conv').value = '';
      }
      updateTranscript();
    }
    function setMerchantReply(text){
      document.getElementById('msg').value = text;
    }
    async function reply(){
      if(!document.getElementById('conv').value){
        document.getElementById('replyClean').textContent = 'Generate a bot message first so the conversation ID is available.';
        return;
      }
      const res = await fetch('/demo/reply', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({
        conversation_id: document.getElementById('conv').value,
        merchant_id: null,
        customer_id: null,
        from_role: 'merchant',
        message: document.getElementById('msg').value,
        received_at: new Date().toISOString(),
        turn_number: 2
      })});
      const data = await res.json();
      lastReply = data;
      document.getElementById('replyOut').textContent = JSON.stringify(data, null, 2);
      document.getElementById('replyClean').textContent = data.body || `Action: ${data.action}`;
      updateTranscript();
    }
    function updateTranscript(){
      const selected = triggerMap[document.getElementById('trigger').value] || {};
      const merchantReply = document.getElementById('msg') ? document.getElementById('msg').value : '';
      const lines = [
        'Judge this prototype bot response using the 50-point challenge rubric.',
        '',
        `Scenario: ${selected.id || 'not selected'} (${selected.kind || 'unknown'})`,
        `Merchant ID: ${selected.merchant_id || 'unknown'}`,
        '',
        'Initial bot message:',
        lastAction ? lastAction.body : '[not generated yet]',
        '',
        `Initial CTA: ${lastAction ? lastAction.cta : '[not generated yet]'}`,
        `Initial rationale: ${lastAction ? lastAction.rationale : '[not generated yet]'}`,
        '',
        'Merchant reply:',
        merchantReply || '[not entered yet]',
        '',
        'Bot follow-up reply:',
        lastReply ? (lastReply.body || `Action: ${lastReply.action}`) : '[not generated yet]',
        '',
        `Follow-up CTA: ${lastReply && lastReply.cta ? lastReply.cta : '[not generated yet]'}`,
        `Follow-up rationale: ${lastReply && lastReply.rationale ? lastReply.rationale : '[not generated yet]'}`,
      ];
      document.getElementById('transcript').value = lines.join('\\n');
    }
    async function copyTranscript(){
      await navigator.clipboard.writeText(document.getElementById('transcript').value);
    }
    function resetDemo(){
      lastAction = null;
      lastReply = null;
      document.getElementById('conv').value = '';
      document.getElementById('msg').value = 'Yes please send it';
      document.getElementById('tickClean').textContent = 'Pick a scenario and generate a bot message.';
      document.getElementById('replyClean').textContent = 'Generate a bot message first, then send a merchant reply.';
      document.getElementById('replyOut').textContent = '';
      updateTranscript();
    }
    document.addEventListener('input', event => {
      if(event.target && event.target.id === 'msg') updateTranscript();
    });
    loadTriggers();
  </script>
</body>
</html>"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def compact(text: str, limit: int = 320) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip(" ,.;") + "…"


def no_ansi(text: str) -> str:
    return text.replace("—", "-").replace("’", "'").replace("“", '"').replace("”", '"')


def load_preload_dir(root: str) -> None:
    base = Path(root).expanduser()
    if not base.exists():
        print(f"Preload dir not found: {base}")
        return
    specs = [
        ("category", base / "categories", lambda d: d["slug"]),
        ("merchant", base / "merchants", lambda d: d["merchant_id"]),
        ("customer", base / "customers", lambda d: d["customer_id"]),
        ("trigger", base / "triggers", lambda d: d["id"]),
    ]
    loaded = 0
    for scope, folder, get_id in specs:
        if not folder.exists():
            continue
        for path in folder.glob("*.json"):
            payload = json.loads(path.read_text())
            context_id = get_id(payload)
            contexts[(scope, context_id)] = {"version": 1, "payload": payload, "stored_at": now_iso()}
            loaded += 1
    print(f"Preloaded {loaded} contexts from {base}")


def gemini_compose(
    category: dict[str, Any],
    merchant: dict[str, Any],
    trigger: dict[str, Any],
    customer: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not GEMINI_API_KEY:
        return None
    prompt = {
        "task": "Compose one chat message for the magicpin Vera challenge. Return strict JSON only.",
        "constraints": [
            "body <= 320 chars",
            "single primary CTA",
            "no URLs",
            "no fabricated facts",
            "use only provided contexts",
            "be specific, category-correct, merchant-fit, trigger-relevant, high-compulsion",
        ],
        "required_json": {"body": "string", "cta": "binary|open_ended|none", "rationale": "string"},
        "category": category,
        "merchant": merchant,
        "trigger": trigger,
        "customer": customer,
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": json.dumps(prompt, ensure_ascii=False)}]}],
        "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
    }
    try:
        req = request.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST")
        req.add_header("Content-Type", "application/json")
        with request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        parsed = json.loads(text)
        if not parsed.get("body"):
            return None
        parsed["body"] = compact(money_safe(parsed["body"]))
        parsed["cta"] = parsed.get("cta") or cta_for(trigger.get("kind", ""), customer)
        parsed["send_as"] = "merchant_on_behalf" if customer else "vera"
        parsed["suppression_key"] = trigger.get("suppression_key", trigger.get("id", ""))
        parsed["rationale"] = parsed.get("rationale", "Gemini-composed from provided contexts.")
        LAST_GEMINI_STATUS.update({"ok": True, "error": None})
        return parsed
    except (error.URLError, KeyError, json.JSONDecodeError, TimeoutError, ValueError) as exc:
        LAST_GEMINI_STATUS.update({"ok": False, "error": str(exc)})
        print(f"Gemini compose failed, falling back to rules: {exc}")
        return None


def money_safe(text: str) -> str:
    return text.replace("₹", "Rs ")


def first_name(merchant: dict[str, Any]) -> str:
    identity = merchant.get("identity", {})
    return identity.get("owner_first_name") or identity.get("name", "there").split()[0].strip(",")


def salutation(merchant: dict[str, Any], category: dict[str, Any] | None = None) -> str:
    first = first_name(merchant)
    slug = (category or {}).get("slug") or merchant.get("category_slug", "")
    if slug == "dentists" and not first.lower().startswith("dr"):
        return f"Dr. {first}"
    return first


def active_offer(merchant: dict[str, Any], category: dict[str, Any] | None = None) -> str:
    for offer in merchant.get("offers", []):
        if offer.get("status") == "active":
            return money_safe(offer.get("title", "your current offer"))
    if category:
        for offer in category.get("offer_catalog", []):
            if offer.get("type") in {"service_at_price", "membership", "free_service"}:
                return money_safe(offer.get("title", "your current offer"))
    return "your current offer"


def find_digest_item(category: dict[str, Any], trigger: dict[str, Any]) -> dict[str, Any] | None:
    item_id = (trigger.get("payload") or {}).get("top_item_id")
    digest = category.get("digest", [])
    if item_id:
        for item in digest:
            if item.get("id") == item_id:
                return item
    return digest[0] if digest else None


def pct(value: Any) -> str:
    try:
        return f"{float(value) * 100:.0f}%"
    except Exception:
        return str(value)


def pct1(value: Any) -> str:
    try:
        return f"{float(value) * 100:.1f}%"
    except Exception:
        return str(value)


def cta_for(kind: str, customer: dict[str, Any] | None = None) -> str:
    if customer:
        return "binary"
    if kind in {"research_digest", "cde_opportunity", "curious_ask_due"}:
        return "open_ended"
    return "binary"


def compose_message(
    category: dict[str, Any],
    merchant: dict[str, Any],
    trigger: dict[str, Any],
    customer: dict[str, Any] | None = None,
) -> dict[str, Any]:
    gemini = gemini_compose(category, merchant, trigger, customer)
    if gemini:
        return gemini

    kind = trigger.get("kind", "unknown")
    identity = merchant.get("identity", {})
    name = identity.get("name", "your business")
    owner = salutation(merchant, category)
    perf = merchant.get("performance", {})
    peer = category.get("peer_stats", {})
    city = identity.get("city", "")
    locality = identity.get("locality", "")
    offer = active_offer(merchant, category)
    suppression_key = trigger.get("suppression_key", trigger.get("id", ""))
    send_as = "merchant_on_behalf" if customer else "vera"

    if customer:
        body = compose_customer_message(category, merchant, trigger, customer)
        return {
            "body": body,
            "cta": cta_for(kind, customer),
            "send_as": send_as,
            "suppression_key": suppression_key,
            "rationale": f"Customer-scoped {kind}; uses customer relationship, consent, and merchant offer.",
        }

    if kind == "research_digest":
        item = find_digest_item(category, trigger) or {}
        trial = item.get("trial_n")
        trial_part = f"{trial:,}-patient " if isinstance(trial, int) else ""
        segment = item.get("patient_segment", "customers").replace("_", " ")
        source = item.get("source", "latest category digest")
        title = item.get("title", "new category update")
        count = merchant.get("customer_aggregate", {}).get("high_risk_adult_count")
        count_part = f"your {count} {segment}" if count and "high risk" in segment else f"your {segment}"
        summary = item.get("summary", "")
        reduction = "38%" if "38%" in summary else ""
        finding = f" found {reduction} lower recurrence" if reduction else " is worth reviewing"
        body = (
            f"{owner}, {source}: for {count_part}, a {trial_part}trial{finding}. "
            f"Want me to draft the patient-facing chat?"
        )
    elif kind in {"regulation_change", "supply_alert"}:
        payload = trigger.get("payload", {})
        item = find_digest_item(category, trigger) or payload
        title = item.get("title") or payload.get("title") or "new compliance update"
        source = item.get("source") or payload.get("source") or "category alert"
        body = f"{owner}, {source}: {title}. Want me to draft a 3-step checklist for {name} so your team can verify it today?"
    elif kind in {"perf_dip", "seasonal_perf_dip"}:
        views_delta = pct((perf.get("delta_7d") or {}).get("views_pct", 0))
        ctr = perf.get("ctr")
        avg_ctr = peer.get("avg_ctr")
        ctr_part = f" CTR {pct1(ctr)} vs peer {pct1(avg_ctr)}." if isinstance(ctr, (int, float)) and isinstance(avg_ctr, (int, float)) else ""
        body = f"{owner}, views are {views_delta} this week.{ctr_part} Rather than a flat discount, want me to draft a recovery chat around {offer}?"
    elif kind == "perf_spike":
        views_delta = pct((perf.get("delta_7d") or {}).get("views_pct", 0))
        body = f"{owner}, your views are up {views_delta} this week. This is the right moment to convert interest: want me to draft a short follow-up around {offer}?"
    elif kind in {"festival_upcoming", "ipl_match_today", "category_seasonal"}:
        payload = trigger.get("payload", {})
        event = payload.get("event") or payload.get("match") or payload.get("title") or kind.replace("_", " ")
        body = f"{owner}, {event} is a timely hook for {locality or city}. Want me to draft one chat campaign using {offer}, no generic percentage discount?"
    elif kind in {"curious_ask_due", "dormant_with_vera"}:
        body = f"Quick check, {owner}: what service are customers asking about most this week at {name}? I'll turn your answer into a Google post + 4-line chat reply."
    elif kind in {"active_planning_intent", "milestone_reached"}:
        body = f"{owner}, I can turn this into a ready plan for {name}: offer, audience, and 3-line outreach copy. Want the first draft now?"
    elif kind == "competitor_opened":
        payload = trigger.get("payload", {})
        distance = payload.get("distance_km") or payload.get("distance")
        distance_part = f" {distance}km away" if distance else ""
        strengths = []
        if merchant.get("review_themes"):
            positives = [r["theme"].replace("_", " ") for r in merchant["review_themes"] if r.get("sentiment") == "pos"]
            strengths.extend(positives[:1])
        if active_offer(merchant, category) != "your current offer":
            strengths.append(active_offer(merchant, category))
        strength_part = f" Your visible edge: {', '.join(strengths[:2])}." if strengths else ""
        body = f"{owner}, a competitor signal appeared{distance_part} near {locality or city}.{strength_part} Want a response post?"
    elif kind in {"review_theme_emerged", "gbp_unverified", "renewal_due", "winback_eligible"}:
        signal = ", ".join(merchant.get("signals", [])[:2]) or kind.replace("_", " ")
        body = f"{owner}, I noticed {signal} for {name}. Want me to draft the next best action using only your current business data?"
    else:
        body = f"{owner}, {kind.replace('_', ' ')} is active for {name}. Want me to draft one specific message using {offer}?"

    return {
        "body": no_ansi(compact(body)),
        "cta": cta_for(kind),
        "send_as": send_as,
        "suppression_key": suppression_key,
        "rationale": f"Merchant-scoped {kind}; uses category voice, merchant state, trigger timing, and a single CTA.",
    }


def compose_customer_message(
    category: dict[str, Any],
    merchant: dict[str, Any],
    trigger: dict[str, Any],
    customer: dict[str, Any],
) -> str:
    kind = trigger.get("kind", "customer_followup")
    customer_name = customer.get("identity", {}).get("name", "there")
    merchant_name = merchant.get("identity", {}).get("name", "the clinic")
    offer = active_offer(merchant, category)
    rel = customer.get("relationship", {})
    last_visit = rel.get("last_visit")
    services = rel.get("services_received") or []
    last_service = services[-1] if services else "visit"
    pref = customer.get("preferences", {}).get("preferred_slots", "")

    if kind == "recall_due":
        body = (
            f"Hi {customer_name}, {merchant_name} here. Your {last_service} recall is due"
            f"{' after your last visit on ' + last_visit if last_visit else ''}. "
            f"{offer}. Want us to hold a {pref.replace('_', ' ') or 'convenient'} slot this week?"
        )
    elif kind in {"customer_lapsed_hard", "trial_followup", "wedding_package_followup", "chronic_refill_due"}:
        body = (
            f"Hi {customer_name}, {merchant_name} here. Based on your last {last_service}, "
            f"we have a relevant follow-up ready: {offer}. Should we help you book a {pref.replace('_', ' ') or 'convenient'} slot?"
        )
    else:
        body = f"Hi {customer_name}, {merchant_name} here. We have a timely update for you: {offer}. Should we help you with this today?"
    return compact(body)


def is_auto_reply(message: str, history: list[dict[str, Any]]) -> bool:
    msg = message.lower().strip()
    canned = [
        "thank you for contacting",
        "automated assistant",
        "we will get back",
        "your message has been received",
        "team tak pahuncha",
    ]
    prior_same = sum(1 for turn in history if turn.get("from") in {"merchant", "customer"} and turn.get("msg", "").strip().lower() == msg)
    return prior_same >= 1 or any(term in msg for term in canned)


def classify_reply(message: str, history: list[dict[str, Any]]) -> str:
    msg = message.lower()
    if is_auto_reply(message, history):
        return "auto_reply"
    if any(word in msg for word in ["yes", "ok", "go ahead", "let's do", "lets do", "send", "confirm", "please do", "haan", "chalega"]):
        return "intent_yes"
    if any(word in msg for word in ["not interested", "stop", "no thanks", "don't", "dont", "band", "unsubscribe"]):
        return "no"
    if any(word in msg for word in ["gst", "tax", "loan", "personal", "abuse", "idiot", "stupid"]):
        return "off_topic"
    if "?" in msg or any(word in msg for word in ["how", "what", "why", "kitna", "price", "cost"]):
        return "question"
    return "neutral"


def reply_action(body: dict[str, Any]) -> dict[str, Any]:
    conv_id = body.get("conversation_id", "")
    message = body.get("message", "")
    history = conversations.setdefault(conv_id, [])
    label = classify_reply(message, history)
    history.append({"from": body.get("from_role", "merchant"), "msg": message, "label": label, "ts": body.get("received_at")})
    trigger_id = conv_id.split("_trg_", 1)[1] if "_trg_" in conv_id else ""
    if trigger_id:
        trigger_id = "trg_" + trigger_id
    trigger = contexts.get(("trigger", trigger_id), {}).get("payload", {})
    merchant_id = body.get("merchant_id") or trigger.get("merchant_id")
    merchant = contexts.get(("merchant", merchant_id), {}).get("payload", {}) if merchant_id else {}
    category = contexts.get(("category", merchant.get("category_slug")), {}).get("payload", {}) if merchant else {}
    owner = salutation(merchant, category) if merchant else "there"
    offer = active_offer(merchant, category) if merchant else "the selected offer"

    if label == "auto_reply":
        auto_count = sum(1 for turn in history if turn.get("label") == "auto_reply")
        if auto_count >= 2:
            return {"action": "end", "rationale": "Repeated canned auto-reply detected; ending gracefully instead of wasting turns."}
        return {
            "action": "send",
            "body": "Got it. If the owner or manager is available, I can show the exact opportunity in 2 lines. Should I continue?",
            "cta": "binary",
            "rationale": "One polite attempt after likely auto-reply; asks for human confirmation.",
        }
    if label == "intent_yes":
        kind = trigger.get("kind", "request")
        if kind == "research_digest":
            item = find_digest_item(category, trigger) or {}
            source = item.get("source", "the digest")
            return {
                "action": "send",
                "body": no_ansi(compact(f"Done, {owner}. I’ll pull {source} and draft a patient chat around {active_offer(merchant, category)}. Next: reply CONFIRM after review.")),
                "cta": "binary",
                "rationale": "Explicit yes detected; advances the accepted research-digest task with concrete next step.",
            }
        if kind == "competitor_opened":
            return {
                "action": "send",
                "body": no_ansi(compact(f"Done, {owner}. I’ll draft a response post using your strongest visible proof and {offer}. Next: reply CONFIRM after review.")),
                "cta": "binary",
                "rationale": "Explicit yes detected; routes competitor-response intent directly to action.",
            }
        return {
            "action": "send",
            "body": no_ansi(compact(f"Done, {owner}. I’ll prepare the draft using {offer} and the trigger context. Next: reply CONFIRM after review.")),
            "cta": "binary",
            "rationale": "Explicit yes detected; switches to action instead of further qualification.",
        }
    if label == "no":
        return {"action": "end", "rationale": "Merchant declined or opted out; ending the conversation."}
    if label == "off_topic":
        return {
            "action": "send",
            "body": "I can't help with that here. I’m focused on business growth messages from the provided context. Want me to continue with that?",
            "cta": "binary",
            "rationale": "Keeps scope tight and redirects politely.",
        }
    if label == "question":
        return {
            "action": "send",
            "body": "Fair question. I’ll keep it specific: one message, one offer, one next step, and no made-up claims. Want the draft?",
            "cta": "binary",
            "rationale": "Answers uncertainty and advances to a concrete next step.",
        }
    return {"action": "wait", "wait_seconds": 900, "rationale": "Reply was ambiguous; waiting rather than spamming."}


def auth_ok(headers: Any) -> bool:
    return headers.get("Authorization", "") == f"Bearer {TOKEN}"


class Handler(BaseHTTPRequestHandler):
    server_version = "VeraPrototypeBot/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"{self.address_string()} - {fmt % args}")

    def send_json(self, status: int, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_html(self, status: int, html: str) -> None:
        data = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def read_json(self) -> dict[str, Any] | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            return json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            return None

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            self.send_html(200, INDEX_HTML)
            return
        if path == "/demo/triggers":
            triggers = []
            for (_, context_id), item in contexts.items():
                payload = item.get("payload", {})
                if payload.get("id") == context_id:
                    triggers.append({"id": context_id, "kind": payload.get("kind"), "merchant_id": payload.get("merchant_id")})
            triggers.sort(key=lambda t: t["id"])
            self.send_json(200, {"count": len(triggers), "triggers": triggers[:100]})
            return
        if path == "/v1/healthz":
            counts = {"category": 0, "merchant": 0, "customer": 0, "trigger": 0}
            for scope, _ in contexts:
                counts[scope] = counts.get(scope, 0) + 1
            self.send_json(200, {"status": "ok", "uptime_seconds": int(time.time() - START), "contexts_loaded": counts})
            return
        if path == "/v1/metadata":
            self.send_json(
                200,
                {
                    "team_name": "Prototype Reference Bot",
                    "team_members": ["magicpin challenge prototype"],
                    "model": GEMINI_MODEL if GEMINI_API_KEY else "deterministic-rule-based",
                    "gemini_enabled": bool(GEMINI_API_KEY),
                    "last_gemini_status": LAST_GEMINI_STATUS,
                    "approach": "optional Gemini composer + trigger router + context-grounded fallback templates + reply classifier",
                    "contact_email": "prototype@example.com",
                    "version": "0.1.0",
                    "submitted_url": PUBLIC_URL,
                    "submitted_at": now_iso(),
                },
            )
            return
        self.send_json(404, {"error": "not_found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path in {"/demo/tick", "/demo/reply"}:
            body = self.read_json()
            if body is None:
                self.send_json(400, {"error": "invalid_json"})
                return
            if path == "/demo/tick":
                trigger_ids = body.get("available_triggers", [])[:20]
                if body.get("force"):
                    clear_demo_suppression(trigger_ids)
                self.send_json(200, {"actions": build_actions(trigger_ids)})
            else:
                self.send_json(200, reply_action(body))
            return

        if not auth_ok(self.headers):
            self.send_json(401, {"error": "unauthorized"})
            return
        body = self.read_json()
        if body is None:
            self.send_json(400, {"error": "invalid_json"})
            return

        if path == "/v1/context":
            self.handle_context(body)
        elif path == "/v1/tick":
            self.handle_tick(body)
        elif path == "/v1/reply":
            self.send_json(200, reply_action(body))
        elif path == "/v1/teardown":
            contexts.clear()
            conversations.clear()
            sent_bodies.clear()
            used_suppression_keys.clear()
            self.send_json(200, {"accepted": True, "wiped_at": now_iso()})
        else:
            self.send_json(404, {"error": "not_found"})

    def handle_context(self, body: dict[str, Any]) -> None:
        scope = body.get("scope")
        context_id = body.get("context_id")
        version = body.get("version")
        payload = body.get("payload")
        if scope not in {"category", "merchant", "customer", "trigger"}:
            self.send_json(400, {"accepted": False, "reason": "invalid_scope"})
            return
        if not context_id or not isinstance(version, int) or not isinstance(payload, dict):
            self.send_json(400, {"accepted": False, "reason": "invalid_context_body"})
            return

        key = (scope, context_id)
        current = contexts.get(key)
        if current and current["version"] >= version:
            self.send_json(409, {"accepted": False, "reason": "stale_version", "current_version": current["version"]})
            return
        contexts[key] = {"version": version, "payload": payload, "stored_at": now_iso()}
        self.send_json(200, {"accepted": True, "ack_id": f"ack_{context_id}_v{version}", "stored_at": contexts[key]["stored_at"]})

    def handle_tick(self, body: dict[str, Any]) -> None:
        self.send_json(200, {"actions": build_actions(body.get("available_triggers", [])[:20])})


def build_actions(trigger_ids: list[str]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for trigger_id in trigger_ids[:20]:
        trigger = contexts.get(("trigger", trigger_id), {}).get("payload")
        if not trigger:
            continue
        suppression_key = trigger.get("suppression_key", trigger_id)
        if suppression_key in used_suppression_keys:
            continue
        merchant_id = trigger.get("merchant_id")
        customer_id = trigger.get("customer_id")
        merchant = contexts.get(("merchant", merchant_id), {}).get("payload") if merchant_id else None
        if not merchant:
            continue
        category = contexts.get(("category", merchant.get("category_slug")), {}).get("payload")
        if not category:
            continue
        customer = contexts.get(("customer", customer_id), {}).get("payload") if customer_id else None
        composed = compose_message(category, merchant, trigger, customer)
        conv_id = f"conv_{merchant_id}_{trigger_id}"
        body_text = composed["body"]
        if body_text in sent_bodies.setdefault(conv_id, set()):
            continue
        sent_bodies[conv_id].add(body_text)
        used_suppression_keys.add(suppression_key)
        actions.append(
            {
                "conversation_id": conv_id,
                "merchant_id": merchant_id,
                "customer_id": customer_id,
                "send_as": composed["send_as"],
                "trigger_id": trigger_id,
                "template_name": f"vera_{trigger.get('kind', 'generic')}_v1",
                "template_params": [],
                "body": body_text,
                "cta": composed["cta"],
                "suppression_key": suppression_key,
                "rationale": composed["rationale"],
            }
        )
    return actions


def clear_demo_suppression(trigger_ids: list[str]) -> None:
    for trigger_id in trigger_ids[:20]:
        trigger = contexts.get(("trigger", trigger_id), {}).get("payload")
        if not trigger:
            continue
        used_suppression_keys.discard(trigger.get("suppression_key", trigger_id))
        merchant_id = trigger.get("merchant_id")
        if merchant_id:
            sent_bodies.pop(f"conv_{merchant_id}_{trigger_id}", None)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8080")))
    parser.add_argument("--preload-dir", default="")
    args = parser.parse_args()
    if args.preload_dir:
        load_preload_dir(args.preload_dir)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    model = GEMINI_MODEL if GEMINI_API_KEY else "deterministic-rule-based"
    print(f"Prototype bot listening on http://{args.host}:{args.port} with token {TOKEN!r}; model={model}")
    server.serve_forever()


if __name__ == "__main__":
    main()
