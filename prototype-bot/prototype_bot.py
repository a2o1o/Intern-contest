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
    digest = [item for item in category.get("digest", []) if isinstance(item, dict)]
    kind = trigger.get("kind", "")
    if kind in {"research_digest", "cde_opportunity", "category_seasonal"} and digest:
        desired = {
            "research_digest": {"research", "trend", "tech"},
            "cde_opportunity": {"cde"},
            "category_seasonal": {"seasonal"},
        }.get(kind, set())
        for item in digest:
            if item.get("kind") in desired:
                return item
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
    if customer:
        return "binary"
    if kind in {"research_digest", "cde_opportunity", "curious_ask_due"}:
        return "open_ended"
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
            parts.append(f"{key.replace('_', ' ')}: {format_value(value)}")
    for key, value in payload.items():
        if len(parts) >= 3:
            break
        if key in priority or key.endswith("_id") or key in {"category"}:
            continue
        if value not in (None, "", [], {}):
            parts.append(f"{key.replace('_', ' ')}: {format_value(value)}")
    return compact("; ".join(parts) or "the current trigger", limit)


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
    if kind in {"supply_alert", "regulation_change"}:
        return "verify the checklist"
    if kind in {"active_planning_intent", "milestone_reached"}:
        return "approve the plan"
    if kind in {"perf_dip", "seasonal_perf_dip", "perf_spike", "review_theme_emerged"}:
        return "send the recovery message"
    if kind in {"renewal_due", "winback_eligible", "dormant_with_vera"}:
        return "review the draft"
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
        if kind == "supply_alert" and payload.get("molecule"):
            batches = ", ".join(payload.get("affected_batches", [])[:2]) or "listed batches"
            title = f"{payload.get('molecule')} batches {batches} need verification"
        else:
            title = item.get("title") or payload.get("title") or payload_brief(payload, 90)
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
        payload = trigger.get("payload", {})
        plan = payload.get("intent_topic") or payload.get("metric") or "this plan"
        body = f"{owner}, I can turn {format_value(plan)} into a ready plan for {name}: {offer}, target audience, and 3-line outreach copy. Want the first draft now?"
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
    kind = trigger.get("kind", "")
    payload = trigger.get("payload", {})
    name = merchant.get("identity", {}).get("name", "your business")
    offer = active_offer(merchant, category)
    if kind == "research_digest":
        item = find_digest_item(category, trigger) or {}
        source = item.get("source", "the latest dental digest")
        action = item.get("actionable") or "a timely recall check"
        return compact(
            f"Draft: Hi, {name} here. {source} has a useful update: {action}. "
            f"If this applies to you, reply 1 and we’ll help with {offer}."
        )
    if kind == "active_planning_intent":
        topic = format_value(payload.get("intent_topic") or "weekday offer")
        return compact(
            f"Draft: Office lunch sorted near you - {name} has {offer} for teams. "
            f"Best for {topic}. Reply with headcount and delivery time."
        )
    if kind == "competitor_opened":
        competitor = payload.get("competitor_name", "a nearby competitor")
        return compact(
            f"Draft: {competitor} opened nearby, but your edge is trust and care already visible in reviews. "
            f"Post {offer} with one proof point today. Reply DONE after posting."
        )
    if kind == "renewal_due":
        return compact(
            f"Draft: {owner}, your {payload.get('plan', 'current')} plan renewal is Rs {payload.get('renewal_amount', '?')} "
            f"and due in {payload.get('days_remaining', '?')} days. Want me to keep growth messages active?"
        )
    if kind == "ipl_match_today":
        return compact(
            f"Draft: {payload.get('match', 'Match')} night at {name}: {offer}. "
            f"Order before the rush and we’ll prioritize prep."
        )
    if kind in {"supply_alert", "regulation_change"}:
        item = find_digest_item(category, trigger) or {}
        title = item.get("title") or payload_brief(payload, 80)
        if payload.get("molecule") or payload.get("affected_batches"):
            batches = ", ".join(payload.get("affected_batches", [])[:3]) or "listed batches"
            title = f"{payload.get('molecule', 'item')} batches {batches}"
        return compact(
            f"Draft checklist for {name}: 1) verify {title}, 2) remove doubtful stock, "
            f"3) message impacted customers only with confirmed facts."
        )
    if kind == "review_theme_emerged":
        theme = format_value(payload.get("theme") or "the review issue")
        return compact(f"Draft: Thanks for flagging {theme}. We’ve tightened the process and will personally track your next order/visit. Reply here if it slips again.")
    if kind in {"perf_dip", "seasonal_perf_dip", "perf_spike"}:
        metric = format_value(payload.get("metric") or "interest")
        return compact(f"Draft: Quick update from {name}: {offer}. We’re keeping slots/orders tight this week, so reply YES and we’ll help you book today.")
    customer_id = trigger.get("customer_id")
    customer = contexts.get(("customer", customer_id), {}).get("payload") if customer_id else None
    if customer:
        return compose_customer_message(category, merchant, trigger, customer)
    return compact(f"Draft: {name} update - {offer}. Reply YES and we’ll help you with the next step today.")


def draft_preview(
    owner: str,
    merchant: dict[str, Any],
    category: dict[str, Any],
    trigger: dict[str, Any],
) -> str:
    kind = trigger.get("kind", "")
    offer = active_offer(merchant, category)
    item = find_digest_item(category, trigger) or {}
    context = payload_brief(trigger.get("payload") or {}, 95)
    if kind in {"research_digest", "cde_opportunity"}:
        source = item.get("source", "the referenced digest")
        action = item.get("actionable") or context
        return compact(f"Preview, {owner}: use {source}, mention {action}, then route interested customers to {offer}. Reply CONFIRM and I’ll output the exact customer message.")
    if kind in {"supply_alert", "regulation_change"}:
        return compact(f"Preview, {owner}: 1) state the verified alert, 2) list the exact item/batch/action, 3) tell staff what to check today. Reply CONFIRM for the checklist.")
    if kind == "active_planning_intent":
        return compact(f"Preview, {owner}: audience = nearby office admins, hook = reliable weekday lunch, offer = {offer}, copy = 3 short lines. Reply CONFIRM for the exact draft.")
    if kind == "review_theme_emerged":
        return compact(f"Preview, {owner}: acknowledge the review theme, fix the operational miss, then send a short recovery note using {offer}. Reply CONFIRM for copy.")
    if kind in {"perf_dip", "seasonal_perf_dip", "perf_spike"}:
        return compact(f"Preview, {owner}: use the recent performance signal, avoid panic discounting, and send one targeted message around {offer}. Reply CONFIRM for copy.")
    if kind == "competitor_opened":
        return compact(f"Preview, {owner}: do not match blindly; lead with your proof point, then {offer}. Reply CONFIRM for the response post.")
    return compact(f"Preview, {owner}: I’ll use {context} with {offer}, keep it to one message and one CTA. Reply CONFIRM for the exact draft.")


def contextual_question_reply(
    owner: str,
    merchant: dict[str, Any],
    category: dict[str, Any],
    trigger: dict[str, Any],
) -> str:
    kind = trigger.get("kind", "")
    payload = trigger.get("payload", {})
    offer = active_offer(merchant, category)
    if kind == "renewal_due":
        return compact(f"{owner}, the renewal shown here is Rs {payload.get('renewal_amount', '?')} for the {payload.get('plan', 'current')} plan, due in {payload.get('days_remaining', '?')} days. Want me to draft the renewal message?")
    if kind == "competitor_opened":
        return compact(f"{owner}, the competitor is using {money_safe(payload.get('their_offer', 'a lower offer'))}. I’d avoid matching blindly; we can counter with {offer} plus your proof. Draft it?")
    if kind == "research_digest":
        item = find_digest_item(category, trigger) or {}
        return compact(f"{owner}, this is about using {item.get('source', 'the research digest')} to support a patient-facing chat around {offer}. No extra campaign cost is shown in the data. Want the draft?")
    if kind == "active_planning_intent":
        return compact(f"{owner}, no campaign spend is shown here. The price in the message is the customer-facing offer: {offer}. I can draft the office/team lunch copy from the planning context. Continue?")
    if kind in {"perf_dip", "seasonal_perf_dip"}:
        return compact(f"{owner}, this is not a paid-spend recommendation yet. It is a recovery message around {offer} because {payload.get('metric', 'performance')} moved recently. Want me to draft that first?")
    if kind == "ipl_match_today":
        return compact(f"{owner}, this is about {payload.get('match', 'today’s match')} near {payload.get('venue', 'your locality')}. The current offer is {offer}; I can draft a match-day version without inventing discounts. Continue?")
    if kind == "supply_alert":
        batches = ", ".join(payload.get("affected_batches", [])[:2]) or "the affected batches"
        return compact(f"{owner}, this is about checking {payload.get('molecule', 'the item')} batches {batches}, not a promotion. I can draft a safe staff workflow message. Want that?")
    if kind == "chronic_refill_due":
        meds = ", ".join(payload.get("molecule_list", [])[:3]) or "the monthly medicines"
        return compact(f"{owner}, this is a refill reminder for {meds}; delivery address is already saved. I can draft a confirmation message, not add new medical claims. Continue?")
    return compact(f"{owner}, this is about {readable_kind(kind).lower()} for {merchant_label(merchant)}. The relevant offer/context is {offer}. Want me to draft the next message?")


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

    title = readable_kind(kind)
    summary = f"{merchant_name} has a {readable_kind(kind).lower()} trigger."
    if kind == "research_digest":
        title = "Research digest for dentist"
        summary = f"{identity.get('owner_first_name', 'The owner')} can use a new clinical digest item for {merchant.get('customer_aggregate', {}).get('high_risk_adult_count', 'their')} high-risk adult patients."
    elif kind == "regulation_change":
        title = "Compliance deadline"
        summary = f"A regulation update has a deadline on {payload.get('deadline_iso', 'record')}; turn it into a practical action."
    elif kind == "recall_due":
        title = "Customer recall due"
        summary = f"{customer_name or 'A customer'} is due for {payload.get('service_due', 'a recall').replace('_', ' ')}; available slots are already known."
    elif kind == "perf_dip":
        title = "Performance dip"
        summary = f"{payload.get('metric', 'Performance').title()} is down {abs(int(float(payload.get('delta_pct', 0)) * 100))}% over {payload.get('window', 'recent window')}; propose a concrete recovery action."
    elif kind == "renewal_due":
        title = "Renewal due soon"
        summary = f"{payload.get('plan', 'Plan')} renewal is due in {payload.get('days_remaining', '?')} days for Rs {payload.get('renewal_amount', '?')}."
    elif kind == "festival_upcoming":
        title = f"{payload.get('festival', 'Festival')} planning"
        summary = f"{payload.get('festival', 'A festival')} is upcoming; find a category-relevant angle without fake urgency."
    elif kind == "wedding_package_followup":
        title = "Bridal follow-up"
        summary = f"{customer_name or 'A bridal lead'} completed a trial; wedding date is {payload.get('wedding_date', 'record')}."
    elif kind == "ipl_match_today":
        title = "IPL match day"
        summary = f"{payload.get('match', 'An IPL match')} at {payload.get('venue', 'local venue')}; decide whether to pitch a match-day message."
    elif kind == "active_planning_intent":
        title = "Active planning intent"
        summary = f"Merchant already asked: {payload.get('merchant_last_message', 'what should it look like')}"
    elif kind == "supply_alert":
        title = "Pharmacy supply alert"
        summary = f"{payload.get('molecule', 'A medicine')} has affected batches {', '.join(payload.get('affected_batches', [])[:2])}; avoid medical overreach."
    elif kind == "chronic_refill_due":
        title = "Chronic refill due"
        summary = f"{customer_name or 'A patient'} runs out on {payload.get('stock_runs_out_iso', 'record')}; saved delivery address is available."
    elif kind == "competitor_opened":
        title = "Nearby competitor opened"
        summary = f"{payload.get('competitor_name', 'A competitor')} opened {payload.get('distance_km', '?')} km away with {money_safe(payload.get('their_offer', 'an offer'))}."
    elif kind == "customer_lapsed_hard":
        title = "Customer winback"
        summary = f"{customer_name or 'A customer'} has not visited for {payload.get('days_since_last_visit', '?')} days; draft a no-shame return message."

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
