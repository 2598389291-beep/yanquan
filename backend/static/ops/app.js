const SESSION_KEY = "yanquan.ops.session";

const state = {
  session: null,
  cases: [],
  total: 0,
  page: 1,
  pageSize: 20,
  selectedCase: null,
  agents: [],
  loading: false,
};

const statusMap = {
  pending_assignment: { label: "待认领", className: "pill-pending" },
  in_progress: { label: "处理中", className: "pill-progress" },
  waiting_user: { label: "待用户补充", className: "pill-user" },
  resolved: { label: "已解决", className: "pill-success" },
  closed: { label: "已关闭", className: "pill-closed" },
};

const transitions = {
  pending_assignment: ["in_progress", "closed"],
  in_progress: ["waiting_user", "resolved", "closed"],
  waiting_user: ["in_progress", "resolved", "closed"],
  resolved: ["in_progress", "closed"],
  closed: ["in_progress"],
};

const $ = (selector) => document.querySelector(selector);

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatDate(value) {
  if (!value) return "—";
  return String(value).replace("T", " ");
}

function statusBadge(status) {
  const meta = statusMap[status] || { label: status || "未知", className: "pill-closed" };
  return `<span class="pill ${meta.className}">${escapeHtml(meta.label)}</span>`;
}

function loadSession() {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function saveSession(session) {
  localStorage.setItem(SESSION_KEY, JSON.stringify(session));
  state.session = session;
}

function clearSession() {
  localStorage.removeItem(SESSION_KEY);
  state.session = null;
  state.cases = [];
  state.selectedCase = null;
}

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (state.session?.token) {
    headers.Authorization = `Bearer ${state.session.token}`;
  }
  const response = await fetch(path, { ...options, headers });
  const body = await response.json().catch(() => ({}));
  if (response.status === 401) {
    clearSession();
    showLogin("登录已失效，请重新登录。");
    throw new Error(body.detail || "登录已失效");
  }
  if (!response.ok || body.code !== 0) {
    throw new Error(body.detail || "请求失败");
  }
  return body.data;
}

function showLogin(message = "") {
  closeDrawer();
  $("#app-view").hidden = true;
  $("#login-view").hidden = false;
  $("#login-error").textContent = message;
  $("#password").value = "";
}

function showApp() {
  $("#login-view").hidden = true;
  $("#app-view").hidden = false;
  $("#account-name").textContent =
    state.session.nickname || state.session.email || `账号 ${state.session.userId}`;
  $("#current-role").textContent = state.session.role === "admin" ? "运营管理员" : "客服";
}

function setLoading(isLoading) {
  state.loading = isLoading;
  document.body.classList.toggle("loading", isLoading);
}

function showToast(message) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.hidden = false;
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => {
    toast.hidden = true;
  }, 2600);
}

async function login(event) {
  event.preventDefault();
  const button = $("#login-submit");
  const error = $("#login-error");
  button.disabled = true;
  error.textContent = "";
  try {
    const data = await api("/api/auth/email/login", {
      method: "POST",
      body: JSON.stringify({
        email: $("#email").value.trim(),
        password: $("#password").value,
      }),
    });
    if (!["agent", "admin"].includes(data.role)) {
      throw new Error("该账号没有运营权限，请联系管理员分配客服角色。");
    }
    saveSession({
      token: data.token,
      userId: data.user_id,
      nickname: data.nickname,
      email: data.email,
      role: data.role,
    });
    showApp();
    await loadCases();
  } catch (err) {
    error.textContent = err.message;
  } finally {
    button.disabled = false;
  }
}

async function logout() {
  clearSession();
  closeDrawer();
  showLogin();
}

async function loadCases() {
  setLoading(true);
  const params = new URLSearchParams({
    page: String(state.page),
    page_size: String(state.pageSize),
    case_status: $("#status-filter").value,
    q: $("#search").value.trim(),
  });
  try {
    const data = await api(`/api/operations/cases?${params}`);
    state.cases = data.items;
    state.total = data.total;
    renderCases();
  } catch (err) {
    showToast(err.message);
  } finally {
    setLoading(false);
  }
}

function renderCases() {
  const body = $("#case-rows");
  const empty = $("#empty-state");
  body.innerHTML = state.cases
    .map(
      (item) => `
        <tr data-case-id="${item.id}">
          <td>
            <div class="case-cell">
              <strong>#${item.id} · ${escapeHtml(item.raw_text.slice(0, 42))}</strong>
              <span>${escapeHtml(item.raw_text)}</span>
            </div>
          </td>
          <td class="muted">${escapeHtml(item.category || "未分类")}</td>
          <td>${statusBadge(item.case_status)}</td>
          <td class="muted">${escapeHtml(item.assignee_name || "未分配")}</td>
          <td class="muted">${escapeHtml(formatDate(item.created_at))}</td>
        </tr>`
    )
    .join("");
  empty.hidden = state.cases.length > 0;
  $("#queue-summary").textContent = `共 ${state.total} 件案件`;
  $("#page-label").textContent = `第 ${state.page} 页`;
  $("#prev-page").disabled = state.page <= 1;
  $("#next-page").disabled = state.page * state.pageSize >= state.total;

  body.querySelectorAll("tr").forEach((row) => {
    row.addEventListener("click", () => openCase(Number(row.dataset.caseId)));
  });
}

async function openCase(caseId) {
  setLoading(true);
  try {
    state.selectedCase = await api(`/api/operations/cases/${caseId}`);
    if (state.session.role === "admin") {
      await loadAgents();
    }
    renderDrawer();
    $("#drawer-overlay").hidden = false;
    $("#case-drawer").hidden = false;
  } catch (err) {
    showToast(err.message);
  } finally {
    setLoading(false);
  }
}

async function loadAgents() {
  try {
    const data = await api("/api/operations/agents");
    state.agents = data.items;
  } catch {
    state.agents = [];
  }
}

function renderDrawer() {
  const item = state.selectedCase;
  if (!item) return;
  $("#case-kicker").textContent = `案件 #${item.id}`;
  $("#case-title").textContent = item.category || "未分类案件";
  const legalBasis = Array.isArray(item.legal_basis) ? item.legal_basis : [];
  const actionPath = Array.isArray(item.action_path) ? item.action_path : [];
  const evidence = Array.isArray(item.evidence) ? item.evidence : [];
  const events = Array.isArray(item.events) ? item.events : [];
  const transitionButtons = (transitions[item.case_status] || [])
    .filter((next) => !(next === "in_progress" && item.case_status === "pending_assignment"))
    .map(
      (next) =>
        `<button class="button button-secondary" type="button" data-status="${next}">${escapeHtml(
          statusMap[next]?.label || next
        )}</button>`
    )
    .join("");
  const assignMarkup =
    state.session.role === "admin"
      ? `
        <form id="assign-form" class="assign-form">
          <select id="assignee" aria-label="选择客服">
            <option value="">选择客服</option>
            ${state.agents
              .map(
                (agent) =>
                  `<option value="${agent.id}" ${String(agent.id) === String(item.assignee_id) ? "selected" : ""}>${escapeHtml(
                    agent.nickname || agent.email || agent.phone || `账号 ${agent.id}`
                  )}</option>`
              )
              .join("")}
          </select>
          <button class="button button-primary" type="submit">分派</button>
        </form>`
      : "";

  $("#case-detail").innerHTML = `
    <section class="detail-section">
      <div class="detail-grid">
        <div class="detail-field">
          <span>案件状态</span>
          <strong>${escapeHtml(statusMap[item.case_status]?.label || item.case_status)}</strong>
        </div>
        <div class="detail-field">
          <span>负责人</span>
          <strong>${escapeHtml(item.assignee_name || "未分配")}</strong>
        </div>
        <div class="detail-field">
          <span>用户文书状态</span>
          <strong>${escapeHtml(item.status_label || item.status)}</strong>
        </div>
        <div class="detail-field">
          <span>创建时间</span>
          <strong>${escapeHtml(formatDate(item.created_at))}</strong>
        </div>
      </div>
    </section>

    <section class="detail-section">
      <h3>用户原始描述</h3>
      <p>${escapeHtml(item.raw_text)}</p>
    </section>

    <section class="detail-section">
      <h3>处理动作</h3>
      <div class="action-row">
        ${!item.assignee_id ? '<button id="claim-case" class="button button-primary" type="button">认领案件</button>' : ""}
        ${transitionButtons}
      </div>
      ${assignMarkup}
    </section>

    <section class="detail-section">
      <h3>法条依据</h3>
      <div class="tag-list">
        ${legalBasis.length ? legalBasis.map((law) => `<span class="tag">${escapeHtml(law)}</span>`).join("") : '<span class="muted">暂无</span>'}
      </div>
    </section>

    <section class="detail-section">
      <h3>维权路径</h3>
      <p>${actionPath.length ? actionPath.map((step) => escapeHtml(actionLabel(step))).join("\\n") : "暂无"}</p>
    </section>

    <section class="detail-section">
      <h3>证据材料</h3>
      <p>${evidence.length ? `${evidence.length} 项材料已登记` : "暂无材料"}</p>
    </section>

    <section class="detail-section">
      <h3>操作轨迹</h3>
      <div class="timeline">
        ${
          events.length
            ? events
                .map(
                  (event) => `
                    <div class="timeline-item">
                      <span class="timeline-dot"></span>
                      <div class="timeline-copy">
                        <strong>${escapeHtml(eventLabel(event))}</strong>
                        <span>${escapeHtml(event.actor_nickname || `账号 ${event.actor_id}`)} · ${escapeHtml(formatDate(event.created_at))}</span>
                      </div>
                    </div>`
                )
                .join("")
            : '<span class="muted">暂无操作记录</span>'
        }
      </div>
    </section>
  `;

  $("#claim-case")?.addEventListener("click", claimCase);
  $("#assign-form")?.addEventListener("submit", assignCase);
  $("#case-detail")
    .querySelectorAll("[data-status]")
    .forEach((button) => button.addEventListener("click", () => changeStatus(button.dataset.status)));
}

function eventLabel(event) {
  if (event.action === "claimed") return "客服认领案件";
  if (event.action === "assigned") return "管理员分派案件";
  if (event.action === "status_changed") {
    const from = statusMap[event.from_case_status]?.label || event.from_case_status;
    const to = statusMap[event.to_case_status]?.label || event.to_case_status;
    return `${from} → ${to}`;
  }
  return event.action;
}

function actionLabel(step) {
  if (typeof step === "string") return step;
  if (step && typeof step === "object") {
    return step.action || step.label || step.title || JSON.stringify(step);
  }
  return String(step ?? "");
}

async function mutateCase(path, payload, successMessage) {
  setLoading(true);
  try {
    const updated = await api(path, {
      method: "POST",
      body: payload ? JSON.stringify(payload) : undefined,
    });
    state.selectedCase = updated;
    renderDrawer();
    await loadCases();
    showToast(successMessage);
  } catch (err) {
    showToast(err.message);
  } finally {
    setLoading(false);
  }
}

function claimCase() {
  if (!state.selectedCase) return;
  mutateCase(
    `/api/operations/cases/${state.selectedCase.id}/claim`,
    null,
    "案件已认领"
  );
}

function assignCase(event) {
  event.preventDefault();
  const assigneeId = $("#assignee").value;
  if (!assigneeId || !state.selectedCase) {
    showToast("请选择客服");
    return;
  }
  mutateCase(
    `/api/operations/cases/${state.selectedCase.id}/assign`,
    { assignee_id: assigneeId },
    "案件已分派"
  );
}

function changeStatus(nextStatus) {
  if (!state.selectedCase) return;
  mutateCase(
    `/api/operations/cases/${state.selectedCase.id}/status`,
    { case_status: nextStatus },
    "案件状态已更新"
  );
}

function closeDrawer() {
  $("#drawer-overlay").hidden = true;
  $("#case-drawer").hidden = true;
  state.selectedCase = null;
}

function bindEvents() {
  $("#login-form").addEventListener("submit", login);
  $("#logout").addEventListener("click", logout);
  $("#filters").addEventListener("submit", (event) => {
    event.preventDefault();
    state.page = 1;
    loadCases();
  });
  $("#refresh").addEventListener("click", loadCases);
  $("#prev-page").addEventListener("click", () => {
    if (state.page > 1) {
      state.page -= 1;
      loadCases();
    }
  });
  $("#next-page").addEventListener("click", () => {
    if (state.page * state.pageSize < state.total) {
      state.page += 1;
      loadCases();
    }
  });
  $("#close-drawer").addEventListener("click", closeDrawer);
  $("#drawer-overlay").addEventListener("click", closeDrawer);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeDrawer();
  });
}

async function init() {
  bindEvents();
  state.session = loadSession();
  if (!state.session?.token) {
    showLogin();
    return;
  }
  showApp();
  await loadCases();
}

init();
