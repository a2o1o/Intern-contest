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
    :root{--green:#173f2f;--accent:#2d6a4f;--paper:#f7f5f0;--line:#e6e1d8;--muted:#66645f;--chat:#efe7dc}
    html,body{height:100%}
    body{font-family:Inter,system-ui,sans-serif;margin:0;background:var(--paper);color:#171717;overflow:hidden}
    main{height:100vh;display:grid;grid-template-rows:auto 1fr;padding:18px;box-sizing:border-box}
    h1{font-size:30px;line-height:1;margin:0 0 6px}
    h2{font-size:24px;margin:0 0 12px}
    p{color:var(--muted);line-height:1.55}
    button,select,input,textarea{font:inherit}
    button{background:var(--accent);color:#fff;border:0;border-radius:8px;padding:10px 14px;font-weight:800;cursor:pointer}
    button.secondary{background:#edf3ef;color:var(--green);border:1px solid #c9ded5}
    button.quick{background:#fff;color:var(--green);border:1px solid #cfc9bd;font-weight:750;padding:8px 11px}
    select,input,textarea{border:1px solid #d0ccc4;border-radius:8px;padding:10px;background:white}
    select{width:100%}
    textarea{width:100%;min-height:160px;box-sizing:border-box;line-height:1.45}
    pre{white-space:pre-wrap;background:#102b21;color:#fff;border-radius:8px;padding:14px;overflow:auto}
    .muted{font-size:13px;color:var(--muted)}
    .intro{display:flex;justify-content:space-between;gap:18px;align-items:end;margin-bottom:14px}
    .intro p{max-width:760px;margin:0}
    .shell{min-height:0;display:grid;grid-template-columns:320px minmax(420px,1fr) 360px;gap:0;background:#fff;border:1px solid var(--line);border-radius:10px;overflow:hidden;box-shadow:0 18px 50px rgba(23,63,47,.16)}
    .panel{background:#fff;border-left:1px solid var(--line);padding:18px;overflow:auto}
    .leftbar{background:#f8f6f1;border-right:1px solid var(--line);display:grid;grid-template-rows:auto 1fr;min-height:0}
    .leftTop{padding:18px;border-bottom:1px solid var(--line)}
    .scenarioBrief{margin-top:12px;background:#fff;border:1px solid #e5ded2;border-radius:8px;padding:12px}
    .scenarioTitle{font-weight:900;color:#173f2f;margin-bottom:6px}
    .contextLine{font-size:13px;color:#555;margin-top:4px}
    .scenarioList{overflow:auto;padding:10px}
    .scenarioItem{width:100%;text-align:left;background:#fff;color:#171717;border:1px solid #e5ded2;border-radius:8px;padding:12px;margin-bottom:8px;font-weight:750}
    .scenarioItem.active{border-color:#2d6a4f;background:#e8f0ee;color:#173f2f}
    .scenarioItem span{display:block;margin-top:4px;font-size:12px;color:#666;font-weight:650;line-height:1.35}
    .chatArea{min-height:0;background:var(--chat);display:grid;grid-template-rows:auto 1fr auto}
    .chatHead{background:#173f2f;color:#fff;padding:14px 16px;display:flex;gap:12px;align-items:center}
    .avatar{width:38px;height:38px;border-radius:50%;background:#e8f0ee;color:#173f2f;display:grid;place-items:center;font-weight:900}
    .chatTitle{font-weight:900}
    .status{font-size:12px;color:#cfe2d8;margin-top:2px}
    .messages{padding:28px clamp(24px,5vw,80px);overflow:auto;display:flex;flex-direction:column;gap:10px;background:
      linear-gradient(rgba(239,231,220,.92),rgba(239,231,220,.92)),
      radial-gradient(circle at 20% 15%,rgba(45,106,79,.10) 0 2px,transparent 3px)}
    .bubble{border-radius:9px;padding:11px 13px;line-height:1.42;max-width:min(680px,72%);box-shadow:0 1px 1px rgba(0,0,0,.08);font-size:15px}
    .bot{align-self:flex-start;background:#fff;color:#171717;border-top-left-radius:2px}
    .merchant{align-self:flex-end;background:#d9fdd3;color:#171717;border-top-right-radius:2px}
    .meta{display:block;text-align:right;color:#777;font-size:10px;margin-top:5px}
    .empty{margin:auto;text-align:center;color:#4d4a43;background:rgba(255,255,255,.7);padding:18px;border-radius:10px;max-width:270px}
    .composer{background:#f5efe7;border-top:1px solid #ddd3c4;padding:12px clamp(18px,4vw,56px);display:grid;gap:9px}
    .quickRow{display:flex;gap:7px;overflow:auto;padding-bottom:2px}
    .sendRow{display:grid;grid-template-columns:1fr auto;gap:8px}
    .sendRow input{min-width:0;border-radius:999px;padding:12px 16px}
    .sendRow button{border-radius:999px;min-width:58px}
    .judge{display:grid;gap:14px}
    .label{font-size:12px;font-weight:900;color:var(--accent);text-transform:uppercase;letter-spacing:.04em;margin-bottom:7px}
    details{margin-top:12px}
    summary{cursor:pointer;color:var(--accent);font-weight:900}
    code{background:#f2eee6;border-radius:4px;padding:1px 5px}
    @media(max-width:1100px){body{overflow:auto}main{height:auto}.shell{grid-template-columns:280px 1fr}.judge{display:none}.chatArea{min-height:720px}}
    @media(max-width:760px){main{padding:10px}.intro{display:block}.shell{grid-template-columns:1fr}.leftbar{display:none}.chatArea{min-height:calc(100vh - 120px)}h1{font-size:28px}.bubble{max-width:88%}.messages{padding:18px 12px}.composer{padding:10px}}
  </style>
</head>
<body>
  <main>
    <div class="intro">
      <div>
        <h1>Vera Prototype Bot</h1>
        <p>Test the candidate experience as a chat, not as raw API calls. Select a scenario, start the assistant, reply like a merchant, then export the transcript for judging.</p>
      </div>
      <button onclick="tick()">Start selected scenario</button>
    </div>
    <div class="shell">
      <aside class="leftbar">
        <div class="leftTop">
          <h2>Scenarios</h2>
          <p class="muted">Choose one test trigger, then start the chat.</p>
          <select id="trigger"></select>
          <div id="scenarioBrief" class="scenarioBrief"></div>
          <div style="display:flex;gap:10px;margin-top:10px">
            <button onclick="tick()">Start chat</button>
            <button class="secondary" onclick="resetDemo()">Reset</button>
          </div>
        </div>
        <div id="scenarioList" class="scenarioList"></div>
      </aside>
      <section class="chatArea" aria-label="Chat demo">
        <div class="chatHead">
          <div class="avatar">V</div>
          <div>
            <div class="chatTitle">Vera assistant</div>
            <div class="status" id="status">Ready for scenario</div>
          </div>
        </div>
        <div id="messages" class="messages">
          <div class="empty">Pick a scenario and press Start chat. The bot's first message will appear here.</div>
        </div>
        <div class="composer">
          <div class="quickRow">
            <button class="quick" onclick="sendQuick('Yes please send it')">Interested</button>
            <button class="quick" onclick="sendQuick('Thank you for contacting us. We will get back to you soon.')">Auto-reply</button>
            <button class="quick" onclick="sendQuick('How much will this cost?')">Pricing</button>
            <button class="quick" onclick="sendQuick('Can you also help me file GST?')">Off-topic</button>
            <button class="quick" onclick="sendQuick('Not interested')">Decline</button>
          </div>
          <div class="sendRow">
            <input id="msg" placeholder="Reply as the merchant" value="" onkeydown="if(event.key==='Enter') reply()" />
            <button onclick="reply()">Send</button>
          </div>
        </div>
      </section>
      <aside class="judge">
        <div class="panel">
          <h2>Judge packet</h2>
          <p class="muted">Paste this into the judging chat when you want a score. It updates as the conversation changes.</p>
          <textarea id="transcript" readonly>Start a chat to build the transcript.</textarea>
          <div style="margin-top:12px">
            <button onclick="copyTranscript()">Copy judge packet</button>
          </div>
        </div>
        <div class="panel">
          <h2>Contract endpoints</h2>
          <pre>GET  /v1/healthz
GET  /v1/metadata
POST /v1/context
POST /v1/tick
POST /v1/reply</pre>
          <details>
            <summary>Raw /v1/tick JSON</summary>
            <pre id="tickOut">Loading triggers...</pre>
          </details>
          <details>
            <summary>Raw /v1/reply JSON</summary>
            <pre id="replyOut"></pre>
          </details>
        </div>
      </div>
    </div>
  </main>
  <script>
    let lastAction = null;
    let lastReply = null;
    let triggerMap = {};
    let chatMessages = [];

    function escapeHtml(value){
      return String(value || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    }
    function triggerLabel(t){
      return `${t.title || t.kind || 'Scenario'} | ${t.merchant_name || t.merchant_id || 'merchant'}`;
    }
    async function loadTriggers(){
      const res = await fetch('/demo/triggers');
      const data = await res.json();
      const select = document.getElementById('trigger');
      triggerMap = Object.fromEntries(data.triggers.map(t => [t.id, t]));
      select.innerHTML = data.triggers.map(t => `<option value="${escapeHtml(t.id)}">${escapeHtml(triggerLabel(t))}</option>`).join('');
      document.getElementById('scenarioList').innerHTML = data.triggers.slice(0, 30).map(t => `
        <button class="scenarioItem" data-trigger="${escapeHtml(t.id)}" onclick="selectScenario('${escapeHtml(t.id)}')">
          ${escapeHtml(t.title || t.kind || 'Scenario')}
          <span>${escapeHtml(t.subtitle || t.summary || '')}</span>
        </button>
      `).join('');
      select.addEventListener('change', () => selectScenario(select.value, false));
      selectScenario(select.value, false);
      document.getElementById('tickOut').textContent = JSON.stringify(data, null, 2);
      updateTranscript();
    }
    function selectScenario(id, updateSelect = true){
      if(updateSelect) document.getElementById('trigger').value = id;
      document.querySelectorAll('.scenarioItem').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.trigger === id);
      });
      renderScenarioBrief();
      updateTranscript();
    }
    function renderScenarioBrief(){
      const selected = triggerMap[document.getElementById('trigger').value] || {};
      document.getElementById('scenarioBrief').innerHTML = `
        <div class="scenarioTitle">${escapeHtml(selected.title || 'Select a scenario')}</div>
        <div class="contextLine">${escapeHtml(selected.summary || 'This will show the merchant situation before the chat starts.')}</div>
        <div class="contextLine"><strong>Merchant:</strong> ${escapeHtml(selected.merchant_name || 'unknown')}</div>
        <div class="contextLine"><strong>Category:</strong> ${escapeHtml(selected.category || 'unknown')} ${selected.customer_name ? `· <strong>Customer:</strong> ${escapeHtml(selected.customer_name)}` : ''}</div>
        <div class="contextLine"><strong>Trigger:</strong> ${escapeHtml(selected.kind || 'unknown')} · urgency ${escapeHtml(selected.urgency || '-')}</div>
      `;
    }
    function setStatus(text){
      document.getElementById('status').textContent = text;
    }
    function renderChat(){
      const box = document.getElementById('messages');
      if(!chatMessages.length){
        box.innerHTML = '<div class="empty">Pick a scenario and press Start chat. The bot\\'s first message will appear here.</div>';
        return;
      }
      box.innerHTML = chatMessages.map(m => `
        <div class="bubble ${m.role}">
          ${escapeHtml(m.text)}
          <span class="meta">${m.role === 'bot' ? 'Vera' : 'Merchant'} · now</span>
        </div>
      `).join('');
      box.scrollTop = box.scrollHeight;
    }
    async function tick(){
      const id = document.getElementById('trigger').value;
      lastAction = null;
      lastReply = null;
      chatMessages = [];
      renderChat();
      document.getElementById('replyOut').textContent = '';
      setStatus('Generating first message...');
      const res = await fetch('/demo/tick', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({available_triggers:[id], force:true})});
      const data = await res.json();
      document.getElementById('tickOut').textContent = JSON.stringify(data, null, 2);
      if(data.actions && data.actions[0]) {
        lastAction = data.actions[0];
        chatMessages.push({role:'bot', text:lastAction.body});
        setStatus('Waiting for merchant reply');
      } else {
        chatMessages.push({role:'bot', text:'No message sent for this trigger.'});
        setStatus('No action');
      }
      renderChat();
      updateTranscript();
    }
    function sendQuick(text){
      document.getElementById('msg').value = text;
      reply();
    }
    async function reply(){
      if(!lastAction){
        setStatus('Start a scenario first');
        return;
      }
      const merchantText = document.getElementById('msg').value.trim();
      if(!merchantText) return;
      chatMessages.push({role:'merchant', text:merchantText});
      renderChat();
      setStatus('Vera is replying...');
      const res = await fetch('/demo/reply', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({
        conversation_id: lastAction.conversation_id,
        merchant_id: null,
        customer_id: null,
        from_role: 'merchant',
        message: merchantText,
        received_at: new Date().toISOString(),
        turn_number: chatMessages.length
      })});
      const data = await res.json();
      lastReply = data;
      document.getElementById('replyOut').textContent = JSON.stringify(data, null, 2);
      chatMessages.push({role:'bot', text:data.body || `Action: ${data.action}`});
      renderChat();
      setStatus(data.action === 'end' ? 'Conversation ended' : 'Waiting for merchant reply');
      updateTranscript();
    }
    function updateTranscript(){
      const selected = triggerMap[document.getElementById('trigger').value] || {};
      const merchantReply = document.getElementById('msg') ? document.getElementById('msg').value : '';
      const lines = [
        'Judge this prototype bot response using the 50-point challenge rubric.',
        '',
        `Scenario: ${selected.title || selected.id || 'not selected'} (${selected.kind || 'unknown'})`,
        `Situation: ${selected.summary || 'unknown'}`,
        `Merchant: ${selected.merchant_name || selected.merchant_id || 'unknown'}`,
        `Category: ${selected.category || 'unknown'}`,
        `Customer: ${selected.customer_name || 'none'}`,
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
      chatMessages = [];
      document.getElementById('msg').value = '';
      document.getElementById('replyOut').textContent = '';
      setStatus('Ready for scenario');
      renderChat();
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
    return text.replace("—", "-").replace("’", "'").replace("“", '"').replace("”", '"').replace("…", "...")


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
    return first_name(merchant)


def active_offer(merchant: dict[str, Any], category: dict[str, Any] | None = None) -> str:
    for offer in merchant.get("offers", []):
        if offer.get("status") == "active":
            return money_safe(offer.get("title", "your current offer"))
    if category:
        for offer in category.get("offer_catalog", []):
            if offer.get("title"):
                return money_safe(offer.get("title", "your current offer"))
    return "your current offer"


def referenced_context_item(category: dict[str, Any], trigger: dict[str, Any]) -> dict[str, Any] | None:
    payload = trigger.get("payload") or {}
    ref_ids = [
        payload.get("top_item_id"),
        payload.get("digest_item_id"),
        payload.get("alert_id"),
        payload.get("content_id"),
        payload.get("item_id"),
    ]
    candidates: list[dict[str, Any]] = []
    for key in ["digest", "patient_content_library", "trend_signals", "seasonal_beats"]:
        values = category.get(key, [])
        if isinstance(values, list):
            candidates.extend(v for v in values if isinstance(v, dict))
    for ref_id in [x for x in ref_ids if x]:
        for item in candidates:
            if item.get("id") == ref_id:
                return item
    return None


def find_digest_item(category: dict[str, Any], trigger: dict[str, Any]) -> dict[str, Any] | None:
    item = referenced_context_item(category, trigger)
    if item:
        return item
    payload = trigger.get("payload") or {}
    if any(payload.get(k) for k in ["title", "source", "summary", "actionable", "molecule", "affected_batches"]):
        return payload
    return None


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
    return "binary"


def payload_brief(payload: dict[str, Any], limit: int = 150) -> str:
    if not payload:
        return "the current trigger"
    priority = [
        "merchant_last_message",
        "title",
        "summary",
        "actionable",
        "match",
        "festival",
        "theme",
        "intent_topic",
        "molecule",
        "metric",
        "season",
    ]
    parts: list[str] = []
    for key in priority:
        value = payload.get(key)
        if value:
            parts.append(f"{human_key(key)}: {format_value(value)}")
    for key, value in payload.items():
        if len(parts) >= 3:
            break
        if key in priority or key.endswith("_id") or key in {"category"}:
            continue
        if value not in (None, "", [], {}):
            parts.append(f"{human_key(key)}: {format_value(value)}")
    return compact("; ".join(parts) or "the current trigger", limit)


def human_key(key: str) -> str:
    labels = {
        "merchant_last_message": "merchant said",
        "intent_topic": "plan",
        "affected_batches": "affected batches",
        "deadline_iso": "deadline",
        "distance_km": "distance",
        "their_offer": "competitor offer",
        "stock_runs_out_iso": "runs out",
    }
    return labels.get(key, key.replace("_", " "))


def source_label(source: Any) -> str:
    value = str(source or "").strip()
    if value.lower() in {"internal", "external", ""}:
        return "provided business context"
    return value


def format_value(value: Any) -> str:
    if isinstance(value, float):
        if -1 < value < 1:
            return pct(value)
        return str(value)
    if isinstance(value, list):
        return ", ".join(format_value(v) for v in value[:3])
    if isinstance(value, dict):
        if "label" in value:
            return str(value["label"])
        return ", ".join(f"{k}: {format_value(v)}" for k, v in list(value.items())[:3])
    return money_safe(str(value).replace("_", " "))


def audience_hint(merchant: dict[str, Any], customer: dict[str, Any] | None = None) -> str:
    if customer:
        return customer.get("identity", {}).get("name", "this customer")
    aggregate = merchant.get("customer_aggregate", {})
    if aggregate.get("high_risk_adult_count"):
        return f"{aggregate['high_risk_adult_count']} high-risk adult patients"
    if aggregate.get("lapsed_90d_plus"):
        return f"{aggregate['lapsed_90d_plus']} lapsed customers"
    if aggregate.get("lapsed_180d_plus"):
        return f"{aggregate['lapsed_180d_plus']} lapsed customers"
    if aggregate.get("delivery_orders_30d"):
        return f"{aggregate['delivery_orders_30d']} recent delivery customers"
    return "the most relevant customers"


def next_step_for(kind: str) -> str:
    return "review the draft"


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

    item = find_digest_item(category, trigger) or {}
    source = source_label(item.get("source") or trigger.get("source") or "provided business context")
    evidence = item.get("title") or item.get("summary") or payload_brief(trigger.get("payload") or {}, 120)
    audience = audience_hint(merchant)
    body = (
        f"{owner}, {source}: {evidence}. For {audience}, I can draft one grounded message "
        f"using {offer}. Reply yes to see the shape."
    )

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

    context = payload_brief(trigger.get("payload") or {}, 100)
    timing = f" after your last visit on {last_visit}" if last_visit else ""
    slot = pref.replace("_", " ") or "convenient"
    body = (
        f"Hi {customer_name}, {merchant_name} here. Based on your last {last_service}{timing}, "
        f"this is relevant now: {context}. {offer}. Should we help you with a {slot} slot?"
    )
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
    yes = any(word in msg for word in ["yes", "ok", "go ahead", "let's do", "lets do", "send", "confirm", "please do", "haan", "chalega", "do it"])
    question = "?" in msg or any(word in msg for word in ["how", "what", "why", "kitna", "price", "cost", "look like"])
    if yes and question:
        return "yes_question"
    if yes:
        return "intent_yes"
    if any(word in msg for word in ["not interested", "stop", "no thanks", "don't", "dont", "band", "unsubscribe"]):
        return "no"
    if any(word in msg for word in ["gst", "tax", "loan", "personal", "abuse", "idiot", "stupid"]):
        return "off_topic"
    if question:
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
    intent_count = sum(1 for turn in history if turn.get("label") == "intent_yes")

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
    if label == "yes_question":
        return {
            "action": "send",
            "body": no_ansi(draft_preview(owner, merchant, category, trigger)),
            "cta": "binary",
            "rationale": "Merchant showed interest but asked for shape/details; previews the concrete plan before asking for confirmation.",
        }
    if label == "intent_yes":
        if "confirm" in message.lower() or intent_count >= 2:
            return {
                "action": "send",
                "body": no_ansi(final_confirmed_draft(owner, merchant, category, trigger)),
                "cta": "none",
                "rationale": "Merchant confirmed the draft; produces the concrete final message instead of repeating the confirmation step.",
            }
        kind = trigger.get("kind", "request")
        return {
            "action": "send",
            "body": no_ansi(draft_preview(owner, merchant, category, trigger)),
            "cta": "binary",
            "rationale": f"Explicit yes detected; previews the {kind} draft and asks for final confirmation.",
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
            "body": no_ansi(contextual_question_reply(owner, merchant, category, trigger)),
            "cta": "binary",
            "rationale": "Answers the question using the active trigger and merchant context before advancing.",
        }
    return {"action": "wait", "wait_seconds": 900, "rationale": "Reply was ambiguous; waiting rather than spamming."}


def final_confirmed_draft(
    owner: str,
    merchant: dict[str, Any],
    category: dict[str, Any],
    trigger: dict[str, Any],
) -> str:
    payload = trigger.get("payload", {})
    name = merchant.get("identity", {}).get("name", "your business")
    offer = active_offer(merchant, category)
    customer_id = trigger.get("customer_id")
    customer = contexts.get(("customer", customer_id), {}).get("payload") if customer_id else None
    if customer:
        return compose_customer_message(category, merchant, trigger, customer)
    item = find_digest_item(category, trigger) or {}
    source = source_label(item.get("source") or trigger.get("source") or "today's update")
    evidence = item.get("actionable") or item.get("summary") or item.get("title") or payload_brief(payload, 120)
    audience = audience_hint(merchant)
    return compact(
        f"Draft: {name} update - {source}: {evidence}. "
        f"For {audience}, use {offer}. Reply YES and we’ll help with the next step."
    )


def draft_preview(
    owner: str,
    merchant: dict[str, Any],
    category: dict[str, Any],
    trigger: dict[str, Any],
) -> str:
    offer = active_offer(merchant, category)
    item = find_digest_item(category, trigger) or {}
    context = payload_brief(trigger.get("payload") or {}, 95)
    source = source_label(item.get("source") or trigger.get("source") or "the provided context")
    action = item.get("actionable") or item.get("summary") or context
    return compact(
        f"Preview, {owner}: source = {source}; audience = {audience_hint(merchant)}; "
        f"message = {action}; offer/context = {offer}. Reply CONFIRM for the exact draft."
    )


def contextual_question_reply(
    owner: str,
    merchant: dict[str, Any],
    category: dict[str, Any],
    trigger: dict[str, Any],
) -> str:
    payload = trigger.get("payload", {})
    offer = active_offer(merchant, category)
    item = find_digest_item(category, trigger) or {}
    source = source_label(item.get("source") or trigger.get("source") or "the provided context")
    evidence = item.get("summary") or item.get("title") or payload_brief(payload, 120)
    return compact(
        f"{owner}, the data only shows this context: {source} - {evidence}. "
        f"The customer-facing offer/context is {offer}; no extra campaign cost is stated unless the payload says so. Continue?"
    )


def readable_kind(kind: str) -> str:
    return (kind or "trigger").replace("_", " ").title()


def merchant_label(merchant: dict[str, Any] | None) -> str:
    if not merchant:
        return "Unknown merchant"
    identity = merchant.get("identity", {})
    name = identity.get("name") or merchant.get("merchant_id") or "Merchant"
    locality = identity.get("locality")
    city = identity.get("city")
    location = ", ".join(x for x in [locality, city] if x)
    return f"{name} ({location})" if location else name


def customer_label(customer: dict[str, Any] | None) -> str | None:
    if not customer:
        return None
    return customer.get("identity", {}).get("name") or customer.get("customer_id")


def demo_trigger_summary(trigger_id: str, trigger: dict[str, Any]) -> dict[str, Any]:
    kind = trigger.get("kind", "trigger")
    payload = trigger.get("payload", {})
    merchant_id = trigger.get("merchant_id")
    customer_id = trigger.get("customer_id")
    merchant = contexts.get(("merchant", merchant_id), {}).get("payload") if merchant_id else None
    customer = contexts.get(("customer", customer_id), {}).get("payload") if customer_id else None
    identity = merchant.get("identity", {}) if merchant else {}
    category = merchant.get("category_slug") if merchant else payload.get("category")
    merchant_name = merchant_label(merchant)
    customer_name = customer_label(customer)
    active = active_offer(merchant or {}, contexts.get(("category", category), {}).get("payload", {}))

    item = find_digest_item(contexts.get(("category", category), {}).get("payload", {}), trigger) or {}
    title = readable_kind(kind)
    summary_source = item.get("title") or item.get("summary") or item.get("actionable") or payload_brief(payload, 180)
    subject = customer_name or merchant_name
    summary = f"{subject}: {summary_source}"

    subtitle = " | ".join(x for x in [merchant_name, category, f"customer: {customer_name}" if customer_name else None, f"offer/context: {active}" if active else None] if x)
    return {
        "id": trigger_id,
        "title": title,
        "summary": compact(summary, 220),
        "subtitle": subtitle,
        "kind": kind,
        "scope": trigger.get("scope"),
        "source": trigger.get("source"),
        "urgency": trigger.get("urgency"),
        "merchant_id": merchant_id,
        "merchant_name": merchant_name,
        "category": category,
        "customer_id": customer_id,
        "customer_name": customer_name,
        "active_offer": active,
    }


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
                    triggers.append(demo_trigger_summary(context_id, payload))
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
