// 바닐라 JS — 프레임워크 없음(요구사항). API_BASE_URL은 config.js에서 온다.

let currentConversationId = null;

async function api(path, options = {}) {
  const resp = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${resp.status}`);
  }
  if (resp.status === 204) return null;
  return resp.json();
}

// --- 데이터 요약 ---
async function refreshSummary() {
  const s = await api("/api/data/summary");
  document.getElementById("s-count").textContent = `${s.count}건`;
  document.getElementById("s-period").textContent =
    s.date_from ? `${s.date_from} ~ ${s.date_to}` : "-";
  document.getElementById("s-mean").textContent = s.mean != null ? s.mean.toFixed(2) : "-";
  document.getElementById("s-maxmin").textContent =
    s.max != null ? `${s.max.toFixed(1)} / ${s.min.toFixed(1)}` : "-";
  document.getElementById("s-trend").textContent = s.trend;
}

// --- 데이터 관리(CRUD) ---
async function refreshDataList() {
  const rows = await api("/api/data");
  const list = document.getElementById("data-list");
  const recent = rows.slice(-15).reverse(); // 최신 15건만 화면에 표시(전체는 502건+)
  list.innerHTML = recent.map(r => `
    <li>
      <span>${r.date} · ${r.value}${r.memo ? ` · ${r.memo}` : ""}</span>
      <button data-del="${r.id}">삭제</button>
    </li>
  `).join("");
  document.getElementById("data-count-hint").textContent =
    `전체 ${rows.length}건 중 최근 15건 표시`;

  list.querySelectorAll("button[data-del]").forEach(btn => {
    btn.onclick = async () => {
      await api(`/api/data/${btn.dataset.del}`, { method: "DELETE" });
      await Promise.all([refreshDataList(), refreshSummary()]);
    };
  });
}

document.getElementById("data-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const date = document.getElementById("data-date").value;
  const value = parseFloat(document.getElementById("data-value").value);
  const memo = document.getElementById("data-memo").value || null;
  await api("/api/data", { method: "POST", body: JSON.stringify({ date, value, memo }) });
  document.getElementById("data-form").reset();
  await Promise.all([refreshDataList(), refreshSummary()]);
});

// --- 대화 기록 ---
async function refreshConversationList() {
  const rows = await api("/api/conversations");
  const list = document.getElementById("conversation-list");
  list.innerHTML = rows.map(r => `
    <li data-id="${r.id}" class="${r.id === currentConversationId ? "active" : ""}">
      <span>${r.title} (${r.message_count})</span>
      <button class="del" data-del="${r.id}">×</button>
    </li>
  `).join("") || `<li class="hint" style="cursor:default">아직 대화가 없습니다</li>`;

  list.querySelectorAll("li[data-id]").forEach(li => {
    li.addEventListener("click", (e) => {
      if (e.target.closest("button[data-del]")) return;
      loadConversation(li.dataset.id);
    });
  });
  list.querySelectorAll("button[data-del]").forEach(btn => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      await api(`/api/conversations/${btn.dataset.del}`, { method: "DELETE" });
      if (currentConversationId === btn.dataset.del) startNewChat();
      await refreshConversationList();
    });
  });
}

async function loadConversation(convId) {
  const conv = await api(`/api/conversations/${convId}`);
  currentConversationId = conv.id;
  const box = document.getElementById("messages");
  box.innerHTML = conv.messages.map(renderBubble).join("");
  box.scrollTop = box.scrollHeight;
  await refreshConversationList();
}

function startNewChat() {
  currentConversationId = null;
  document.getElementById("messages").innerHTML = "";
  refreshConversationList();
}
document.getElementById("new-chat-btn").addEventListener("click", startNewChat);

// --- 채팅 ---
function renderBubble(m) {
  return `<div class="msg ${m.role}">${escapeHtml(m.content)}</div>`;
}
function escapeHtml(s) {
  return s.replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

document.getElementById("chat-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = document.getElementById("chat-input");
  const message = input.value.trim();
  if (!message) return;

  const box = document.getElementById("messages");
  box.insertAdjacentHTML("beforeend", renderBubble({ role: "user", content: message }));
  input.value = "";
  const submitBtn = e.target.querySelector("button");
  submitBtn.disabled = true;

  const loadingEl = document.createElement("div");
  loadingEl.className = "msg assistant loading";
  loadingEl.textContent = "생각하는 중...";
  box.appendChild(loadingEl);
  box.scrollTop = box.scrollHeight;

  try {
    const resp = await api("/api/chat", {
      method: "POST",
      body: JSON.stringify({ message, conversation_id: currentConversationId }),
    });
    currentConversationId = resp.conversation_id;
    loadingEl.remove();
    box.insertAdjacentHTML("beforeend", renderBubble({ role: "assistant", content: resp.answer }));
    await refreshConversationList();
  } catch (err) {
    loadingEl.textContent = `오류: ${err.message}`;
    loadingEl.classList.remove("loading");
  } finally {
    submitBtn.disabled = false;
    box.scrollTop = box.scrollHeight;
  }
});

// --- 보너스: 다크 모드 ---
document.getElementById("theme-toggle").addEventListener("click", () => {
  const root = document.documentElement;
  const isDark = root.getAttribute("data-theme") === "dark";
  root.setAttribute("data-theme", isDark ? "light" : "dark");
  localStorage.setItem("theme", isDark ? "light" : "dark");
});
const savedTheme = localStorage.getItem("theme");
if (savedTheme) document.documentElement.setAttribute("data-theme", savedTheme);

// --- 보너스: 데이터 CSV 내보내기 ---
document.getElementById("export-btn").addEventListener("click", async () => {
  const rows = await api("/api/data");
  const header = "id,date,value,memo\n";
  const body = rows.map(r => `${r.id},${r.date},${r.value},"${(r.memo || "").replace(/"/g, '""')}"`).join("\n");
  const blob = new Blob([header + body], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "data_export.csv";
  a.click();
  URL.revokeObjectURL(url);
});

// --- 초기화 ---
(async function init() {
  document.getElementById("data-date").value = new Date().toISOString().slice(0, 10);
  await Promise.all([refreshSummary(), refreshDataList(), refreshConversationList()]);
})();
