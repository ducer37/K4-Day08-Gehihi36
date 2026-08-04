const $ = (s) => document.querySelector(s);
const messages = $("#messages");
const traceBox = $("#trace");
const sourcesBox = $("#sources");
let testcases = [];

function esc(value) {
  return String(value).replace(/[&<>"']/g, (x) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[x]));
}

function config() {
  return {
    top_k: Number($("#topK").value || 5),
    score_threshold: Number($("#threshold").value || 0.48),
    use_reranking: $("#useRerank").checked,
    use_llm: $("#useLlm").checked,
  };
}

function scroll() {
  messages.scrollTop = messages.scrollHeight;
}

function message(text, kind) {
  const el = document.createElement("article");
  el.className = `message ${kind}`;
  el.innerHTML = kind === "assistant"
    ? `<div class="avatar">R</div><div><div class="bubble"><div class="inline-trace"></div><div class="answer-text"></div></div><time>RAG Assistant · streaming</time></div>`
    : `<div><div class="bubble">${esc(text)}</div><time>You</time></div>`;
  messages.append(el);
  scroll();
  return kind === "assistant"
    ? { answer: el.querySelector(".answer-text"), trace: el.querySelector(".inline-trace") }
    : null;
}

function addTrace(t, inlineTrace) {
  if (traceBox.classList.contains("empty")) {
    traceBox.classList.remove("empty");
    traceBox.innerHTML = "";
  }
  const el = document.createElement("div");
  el.className = `trace-item ${t.status}`;
  el.innerHTML = `<i class="trace-dot"></i><div><div class="trace-name">${esc(t.step)} <span class="trace-meta">${esc(t.status)}</span></div><div class="trace-desc">${esc(t.reasoning_summary || "")}</div></div>`;
  traceBox.append(el);
  $("#traceCount").textContent = traceBox.children.length;

  if (inlineTrace) {
    const chip = document.createElement("span");
    chip.className = `trace-chip ${t.status}`;
    chip.textContent = `${t.step}: ${t.status}`;
    inlineTrace.append(chip);
    scroll();
  }
}

function drawSources(items) {
  sourcesBox.classList.remove("empty");
  sourcesBox.innerHTML = items.length
    ? items.map((s, i) => `<article class="source"><div class="source-top"><span>#${i + 1} · ${esc(s.metadata?.source || s.source)}</span><span>${s.match_score ?? 0}% match</span></div><div class="badges"><i class="badge">${esc(s.type)}</i><i class="badge">${esc(s.customer_role)}</i><i class="badge">${esc(s.retrieval_source)}</i><i class="badge">raw ${esc(s.score_kind || "score")}: ${s.score}</i>${s.expected_match ? `<i class="badge good">expected source</i>` : ""}</div><p>${esc(s.content_preview)}</p></article>`).join("")
    : "No evidence matched the configured threshold.";
  $("#sourceCount").textContent = items.length;
}

function metrics(m) {
  const cfg = config();
  $("#metrics").innerHTML = `<div><small>Top K</small><b>${m.top_k ?? cfg.top_k}</b></div><div><small>Threshold</small><b>${m.score_threshold ?? cfg.score_threshold}</b></div><div><small>Rerank</small><b>${m.use_reranking ?? cfg.use_reranking ? "on" : "off"}</b></div><div><small>Sources</small><b>${m.source_count ?? $("#sourceCount").textContent}</b></div>`;
}

function renderTestcases(items) {
  testcases = items || [];
  const select = $("#testcaseSelect");
  select.innerHTML = `<option value="">Chọn testcase...</option>` + testcases
    .map((x) => `<option value="${x.id}">${x.id}. ${esc(x.question)}</option>`)
    .join("");
  $("#caseCount").textContent = testcases.length;
}

function selectedTestcase() {
  return testcases.find((x) => String(x.id) === $("#testcaseSelect").value);
}

function showExpected(item) {
  $("#expectedCase").innerHTML = item
    ? `<b>Expected</b><p>${esc(item.expected_answer)}</p><small>${esc(item.expected_context)}</small>`
    : "Chọn một testcase để nạp câu hỏi mẫu.";
}

async function ask(query) {
  query = query.trim();
  if (!query) return;

  message(query, "user");
  $("#query").value = "";
  $("#sendBtn").disabled = true;
  const assistant = message("", "assistant");
  assistant.trace.innerHTML = `<span class="trace-chip running">agent started</span>`;
  traceBox.className = "trace";
  traceBox.innerHTML = "";
  $("#traceCount").textContent = "0";
  drawSources([]);
  metrics({});

  try {
    const params = new URLSearchParams({ query, ...config() });
    const response = await fetch(`/api/chat/stream?${params.toString()}`);
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let pending = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      pending += decoder.decode(value, { stream: true });
      const events = pending.split("\n\n");
      pending = events.pop();
      for (const raw of events) {
        const kind = (raw.match(/^event: (.+)$/m) || [])[1];
        const data = (raw.match(/^data: (.+)$/m) || [])[1];
        if (!data) continue;
        const payload = JSON.parse(data);
        if (kind === "delta") {
          assistant.answer.textContent += payload.text;
          scroll();
        }
        if (kind === "trace") addTrace(payload, assistant.trace);
        if (kind === "complete") {
          drawSources(payload.sources);
          metrics({ ...payload.metrics, source_count: payload.sources.length });
          assistant.trace.querySelector(".running")?.remove();
        }
      }
    }
  } catch (e) {
    assistant.answer.textContent = "Unable to reach the local demo server.";
  } finally {
    $("#sendBtn").disabled = false;
  }
}

$("#chatForm").addEventListener("submit", (e) => {
  e.preventDefault();
  ask($("#query").value);
});
$("#query").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    ask(e.target.value);
  }
});
document.querySelectorAll(".suggestions button").forEach((b) => {
  b.onclick = () => ask(b.textContent);
});
$("#testcaseSelect").addEventListener("change", () => {
  const item = selectedTestcase();
  showExpected(item);
  if (item) $("#query").value = item.question;
});
$("#loadCaseBtn").onclick = () => {
  const item = selectedTestcase();
  if (item) ask(item.question);
};
$("#clearBtn").onclick = () => {
  messages.innerHTML = "";
  traceBox.className = "trace empty";
  traceBox.textContent = "Trace events will appear here.";
  sourcesBox.className = "sources empty";
  sourcesBox.textContent = "Run a query to inspect retrieved evidence.";
  metrics({});
};
$("#exportBtn").onclick = () => window.open("/api/logs", "_blank");

fetch("/api/status")
  .then((r) => r.json())
  .then((s) => {
    $("#checkpoints").innerHTML = s.checkpoints.map((x) => `<section class="cp"><div class="cp-top"><span class="cp-id">${x.id}</span><span class="cp-title">${x.title}</span><i class="dot ${x.state === "attention" ? "attention" : ""}"></i></div><ul>${x.items.map((i) => `<li>${esc(i)}</li>`).join("")}</ul></section>`).join("");
    $("#config").innerHTML = Object.entries(s.config).map(([k, v]) => `${k}: ${v}`).join("<br>");
  })
  .catch(() => {});

fetch("/api/testcases")
  .then((r) => r.json())
  .then((data) => renderTestcases(data.items))
  .catch(() => renderTestcases([]));
