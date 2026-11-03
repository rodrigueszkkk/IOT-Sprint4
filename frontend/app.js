// Painel CLYVO VET — consome a API REST (mesma origem). Atualiza a triagem a cada 4 segundos.
const API = "/api";
const LEVEL_TXT = { 0: "P3 · ESTÁVEL", 1: "P2 · ATENÇÃO", 2: "P1 · CRÍTICO" };
const state = { pets: [], selectedPet: 1, tutorPet: 1 };

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
// Formatação estilo WhatsApp (*negrito* e _itálico_) aplicada sobre texto já escapado
const wa = (s) => esc(s).replace(/\*([^*\n]+)\*/g, "<b>$1</b>").replace(/(^|\s)_([^_\n]+)_/g, "$1<i>$2</i>");
const time = (iso) => new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });

async function api(path, options = {}) {
  const res = await fetch(API + path, { headers: { "Content-Type": "application/json" }, ...options });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

// ------------------------------------------------------------------ abas
document.querySelectorAll(".tab").forEach((btn) =>
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("active", b === btn));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.toggle("active", p.id === `tab-${btn.dataset.tab}`));
    if (btn.dataset.tab === "tutor") loadTutor();
  })
);

// ------------------------------------------------------------- cabeçalho
async function loadHealth() {
  const h = await api("/health");
  const pill = $("pill-llm");
  pill.textContent = h.llm_mode === "gemini" ? `IA Generativa: Gemini (${h.llm_model})` : "IA Generativa: modo offline";
  pill.classList.toggle("offline", h.llm_mode !== "gemini");
  const m = await api("/model/metrics");
  $("pill-model").textContent = `ML: ${m.selected_model} · F1 ${(m.test_f1_macro * 100).toFixed(1)}% · Recall crítico ${(m.test_recall_critico_sistema * 100).toFixed(1)}%`;
  $("pill-model").title = `Recall CRÍTICO do modelo puro: ${(m.test_recall_critico * 100).toFixed(1)}% · com dupla checagem clínica: ${(m.test_recall_critico_sistema * 100).toFixed(1)}%`;
}

async function loadPets() {
  state.pets = await api("/pets");
  for (const id of ["tutor-pet", "sim-pet"]) {
    $(id).innerHTML = state.pets.map((p) => `<option value="${p.id}">${esc(p.name)} (${esc(p.species)})</option>`).join("");
  }
}

// --------------------------------------------------------------- clínica
async function loadTriage() {
  const queue = await api("/triage");
  $("triage-list").innerHTML = queue.map((q) => {
    const l = q.latest;
    return `<li class="triage-item l${q.level} ${q.pet.id === state.selectedPet ? "selected" : ""}" data-pet="${q.pet.id}">
      <div class="row"><b>${esc(q.pet.name)}</b><span class="badge l${q.level}">${LEVEL_TXT[q.level]}</span></div>
      <div class="sub">${esc(q.pet.breed)} · ${q.pet.needs_post_op ? `pós-op D${q.pet.days_post_op}` : "acompanhamento"}</div>
      <div class="sub">${l ? `${l.temperature}°C · ${l.heart_rate} BPM · ${l.movement_level} · ${time(l.created_at)}` : "sem leituras"}
      ${q.open_alerts ? ` · <b>${q.open_alerts} alerta(s) aberto(s)</b>` : ""}</div></li>`;
  }).join("");
  document.querySelectorAll(".triage-item").forEach((li) =>
    li.addEventListener("click", () => { state.selectedPet = Number(li.dataset.pet); refreshClinic(); })
  );
}

function drawChart(readings) {
  const svg = $("chart");
  if (!readings.length) { svg.innerHTML = ""; return; }
  const W = 600, H = 180, pad = 18;
  const x = (i) => pad + (i * (W - 2 * pad)) / Math.max(1, readings.length - 1);
  const scale = (v, lo, hi) => H - pad - ((v - lo) / (hi - lo)) * (H - 2 * pad);
  const tPts = readings.map((r, i) => `${x(i)},${scale(r.temperature, 35, 42)}`).join(" ");
  const hPts = readings.map((r, i) => `${x(i)},${scale(r.heart_rate, 40, 240)}`).join(" ");
  const feverY = scale(39.2, 35, 42);
  const dots = readings.map((r, i) => r.risk_level > 0
    ? `<circle cx="${x(i)}" cy="${scale(r.temperature, 35, 42)}" r="4" fill="${r.risk_level === 2 ? "var(--danger)" : "var(--warn)"}"><title>${r.risk_label} · ${r.temperature}°C · ${r.heart_rate} BPM</title></circle>` : "").join("");
  svg.innerHTML = `
    <line x1="${pad}" x2="${W - pad}" y1="${feverY}" y2="${feverY}" stroke="var(--danger)" stroke-dasharray="4 4" stroke-width="1" opacity=".5"/>
    <text x="${W - pad}" y="${feverY - 4}" text-anchor="end" font-size="10" fill="var(--muted)">limite febre 39,2°C</text>
    <polyline points="${hPts}" fill="none" stroke="var(--hr)" stroke-width="2" vector-effect="non-scaling-stroke" opacity=".85"/>
    <polyline points="${tPts}" fill="none" stroke="var(--temp)" stroke-width="2.5" vector-effect="non-scaling-stroke"/>
    ${dots}`;
}

function renderAlert(alert) {
  if (!alert) { $("alert-detail").innerHTML = '<p class="muted">Nenhum alerta para este paciente. A IA gera o rascunho SOAP automaticamente quando o risco sobe.</p>'; return; }
  const s = alert.soap;
  $("alert-detail").innerHTML = `
    <div class="row-between"><span class="badge l${alert.risk_level}">${esc(alert.priority)}</span>
      ${alert.status === "ABERTO" ? `<button class="btn ghost" id="btn-ack" data-id="${alert.id}">Assumir atendimento</button>` : `<span class="muted small">${esc(alert.status)}</span>`}</div>
    <p class="meta-line">Alerta #${alert.id} · origem: ${esc(alert.source)} · ${time(alert.created_at)} · gerado por ${esc(alert.llm_mode)}</p>
    <div class="soap">
      <h3>S — Subjetivo</h3><p>${esc(s.subjetivo)}</p>
      <h3>O — Objetivo</h3><p>${esc(s.objetivo)}</p>
      <h3>A — Avaliação</h3><p>${esc(s.avaliacao)}</p>
      <h3>P — Plano</h3><ul>${s.plano.map((p) => `<li>${esc(p)}</li>`).join("")}</ul>
    </div>
    <p class="cite">Protocolos citados (RAG): ${(alert.citations || []).map(esc).join(", ") || "—"}</p>`;
  const ack = $("btn-ack");
  if (ack) ack.addEventListener("click", async () => { await api(`/alerts/${ack.dataset.id}/ack`, { method: "PATCH" }); refreshClinic(); });
}

async function loadPatient() {
  const id = state.selectedPet;
  const [pet, readings, alerts] = await Promise.all([api(`/pets/${id}`), api(`/pets/${id}/telemetry?limit=48`), api(`/alerts?pet_id=${id}&limit=5`)]);
  const l = pet.latest;
  $("pt-name").textContent = `${pet.name} — ${pet.breed}`;
  $("pt-meta").textContent = `${pet.species}, ${pet.age} anos, ${pet.weight_kg} kg · Tutor(a): ${pet.tutor_name} · ${pet.needs_post_op ? `pós-operatório D${pet.days_post_op}` : "acompanhamento contínuo"}`;
  $("pt-level").className = `badge l${l ? l.risk_level : 0}`;
  $("pt-level").textContent = l ? LEVEL_TXT[l.risk_level] : "";
  $("v-temp").textContent = l ? `${l.temperature} °C` : "—";
  $("v-hr").textContent = l ? `${l.heart_rate} BPM` : "—";
  $("v-mov").textContent = l ? l.movement_level : "—";
  $("v-conf").textContent = l ? `${Math.round(l.confidence * 100)}%` : "—";
  $("pt-anomalies").innerHTML = l && l.anomalies?.length ? l.anomalies.map((a) => `<span class="chip">${esc(a)}</span>`).join("") : '<span class="chip neutral">Sem anomalias na última leitura</span>';
  $("pt-records").innerHTML = pet.records.map((r) => `<div class="record"><b>${esc(r.record_date)} · ${esc(r.description)}</b><br>${esc(r.diagnosis)}<br><span class="muted">Prescrição: ${esc(r.treatment)} — ${esc(r.veterinarian)}</span></div>`).join("");
  drawChart(readings);
  renderAlert(alerts[0]);
}

async function loadNotifications() {
  const list = await api("/notifications?limit=15");
  $("notif-list").innerHTML = list.map((n) => `<li><span class="ch">${esc(n.channel)}</span> → ${esc(n.recipient)} · ${time(n.created_at)}<br><span class="muted">${esc(n.message.split("\n")[0])}</span></li>`).join("") || '<li class="muted">Nenhuma notificação ainda.</li>';
}

async function refreshClinic() {
  try { await Promise.all([loadTriage(), loadPatient(), loadNotifications()]); } catch (e) { console.error(e); }
}

// ----------------------------------------------------------------- tutor
const SUGGESTIONS = ["Como ele está agora?", "Ele pode subir no sofá?", "Qual o horário do remédio?", "Posso dar paracetamol?", "Ele não quer comer, é normal?", "A ferida está vermelha"];

async function loadTutor() {
  state.tutorPet = Number($("tutor-pet").value || 1);
  const [history, alerts] = await Promise.all([api(`/pets/${state.tutorPet}/chat`), api(`/alerts?pet_id=${state.tutorPet}&limit=10`)]);
  const pet = state.pets.find((p) => p.id === state.tutorPet);
  $("chat-box").innerHTML = history.length ? history.map(msgHtml).join("")
    : `<div class="msg assistant">Oi! Eu sou a assistente da CLYVO VET 🐾 Estou acompanhando o(a) ${esc(pet?.name)} pela coleira. Pode me perguntar sobre a recuperação, a medicação ou qualquer sinal que você notar.</div>`;
  $("chat-box").scrollTop = $("chat-box").scrollHeight;
  $("suggestions").innerHTML = SUGGESTIONS.map((s) => `<button type="button">${esc(s)}</button>`).join("");
  $("suggestions").querySelectorAll("button").forEach((b) => b.addEventListener("click", () => sendChat(b.textContent)));
  $("tutor-alerts").innerHTML = alerts.map((a) => `<li>${wa(a.tutor_message)}<span class="time">${time(a.created_at)}</span></li>`).join("") || '<li class="muted">Nenhum alerta recebido. 💚</li>';
}

function msgHtml(m) {
  return `<div class="msg ${m.role}">${wa(m.content)}${m.llm_mode ? `<span class="mode">${esc(m.llm_mode)}</span>` : ""}</div>`;
}

async function sendChat(text) {
  const message = text.trim();
  if (!message) return;
  $("chat-input").value = "";
  $("chat-box").insertAdjacentHTML("beforeend", msgHtml({ role: "user", content: message }) + '<div class="msg assistant" id="typing">digitando…</div>');
  $("chat-box").scrollTop = $("chat-box").scrollHeight;
  try {
    await api(`/pets/${state.tutorPet}/chat`, { method: "POST", body: JSON.stringify({ message }) });
  } catch (e) {
    console.error(e);
  }
  await loadTutor();
}

$("chat-form").addEventListener("submit", (e) => { e.preventDefault(); sendChat($("chat-input").value); });
$("tutor-pet").addEventListener("change", () => { $("summary-box").innerHTML = '<span class="muted">Clique em “Gerar resumo”.</span>'; loadTutor(); });

$("btn-summary").addEventListener("click", async () => {
  const btn = $("btn-summary");
  btn.disabled = true; btn.textContent = "Analisando…";
  try {
    const s = await api(`/pets/${state.tutorPet}/summary`);
    const st = s.stats || {};
    $("summary-box").innerHTML = `<p>${esc(s.resumo)}</p>
      ${st.leituras ? `<div class="summary-stats"><div><b>${st.temp_min}–${st.temp_max}°C</b>temperatura</div><div><b>${st.fc_media} BPM</b>FC média</div><div><b>${st.pct_repouso}%</b>em repouso</div></div>` : ""}
      ${s.destaques.length ? `<p><b>Destaques</b></p><ul>${s.destaques.map((d) => `<li>${esc(d)}</li>`).join("")}</ul>` : ""}
      ${s.recomendacoes_personalizadas.length ? `<p><b>Recomendações para hoje</b></p><ul>${s.recomendacoes_personalizadas.map((d) => `<li>${esc(d)}</li>`).join("")}</ul>` : ""}
      <p class="cite">Gerado por ${esc(s.llm_mode)}</p>`;
  } finally { btn.disabled = false; btn.textContent = "Gerar resumo"; }
});

// ------------------------------------------------------------- simulador
function showOutput(data) {
  const slim = (r) => ({ pet: r.pet_name, risco: r.risk.risk_label, prioridade: r.risk.triage_priority, confianca: r.risk.confidence,
    probabilidades: r.risk.probabilities, anomalias: r.risk.anomalies, override_seguranca: r.risk.safety_override,
    alerta: r.alert ? { id: r.alert.id, gerado_por: r.alert.llm_mode, mensagem_tutor: r.alert.tutor_message, soap: r.alert.soap, protocolos_rag: (r.alert.retrieved || []).map((k) => `${k.ref} ${k.title} (${k.score})`) } : (r.alert_skipped || "sem alerta (paciente estável)") });
  $("sim-output").textContent = JSON.stringify(Array.isArray(data) ? data.map(slim) : slim(data), null, 2);
}

document.querySelectorAll("[data-scenario]").forEach((btn) =>
  btn.addEventListener("click", async () => {
    btn.disabled = true;
    $("sim-output").textContent = "Processando: modelo preditivo → RAG → IA generativa…";
    try { showOutput(await api(`/simulate/${btn.dataset.scenario}?pet_id=${$("sim-pet").value}`, { method: "POST" })); }
    catch (e) { $("sim-output").textContent = e.message; }
    finally { btn.disabled = false; state.selectedPet = Number($("sim-pet").value); refreshClinic(); }
  })
);

$("in-temp").addEventListener("input", (e) => ($("lbl-temp").textContent = e.target.value));
$("in-hr").addEventListener("input", (e) => ($("lbl-hr").textContent = e.target.value));
$("btn-send").addEventListener("click", async () => {
  const pet = state.pets.find((p) => p.id === Number($("sim-pet").value));
  const payload = { deviceId: pet.device_id, temperature: Number($("in-temp").value), heartRateBpm: Number($("in-hr").value),
    movementLevel: $("in-mov").value, emergencyPressed: $("in-sos").checked };
  $("sim-output").textContent = "Processando…";
  try { showOutput(await api("/telemetry", { method: "POST", body: JSON.stringify(payload) })); }
  catch (e) { $("sim-output").textContent = e.message; }
  state.selectedPet = pet.id; refreshClinic();
});

// ------------------------------------------------------------------ init
(async function init() {
  await Promise.all([loadHealth(), loadPets()]);
  await refreshClinic();
  setInterval(refreshClinic, 4000);
})();
