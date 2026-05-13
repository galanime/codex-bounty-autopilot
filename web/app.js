const money = new Intl.NumberFormat("en-US", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const rtc = (min, max = min) => {
  const same = Number(min || 0) === Number(max || 0);
  return same ? `${Number(min || 0).toFixed(0)} RTC` : `${Number(min || 0).toFixed(0)}-${Number(max || 0).toFixed(0)} RTC`;
};

const byId = (id) => document.getElementById(id);

const statusMap = {
  approved_pending_merge: "已通过，等待合并",
  merged_pending_payout: "已合并，等待发放",
  submitted_pending_review: "已提交，等待审核",
  changes_requested: "需要修改",
  rejected: "已拒绝",
  paid: "已到账",
  unknown: "未知",
};

const verdictMap = {
  "inspect-now": "优先检查",
  maybe: "可观察",
  avoid: "跳过",
};

function setText(id, value) {
  const node = byId(id);
  if (node) node.textContent = value;
}

function statusLabel(status) {
  return statusMap[status] || String(status || "unknown").replaceAll("_", " ");
}

function renderActiveItems(items) {
  const tbody = byId("activeItems");
  tbody.innerHTML = "";
  if (!items.length) {
    tbody.innerHTML = `<tr><td colspan="3" class="empty">当前没有正在跟踪的 PR。</td></tr>`;
    return;
  }
  for (const item of items) {
    const tr = document.createElement("tr");
    const expected = rtc(item.expected_rtc_min, item.expected_rtc_max);
    const label = statusLabel(item.status);
    tr.innerHTML = `
      <td>
        <a href="${item.url || "#"}" target="_blank" rel="noreferrer">${item.repo}#${item.number}</a>
        <div class="meta">${item.title || ""}</div>
      </td>
      <td><span class="status ${item.status || ""}">${label}</span></td>
      <td>${expected}</td>
    `;
    tbody.appendChild(tr);
  }
}

function renderQueue(candidates) {
  const container = byId("candidateQueue");
  container.innerHTML = "";
  setText("queueCount", String(candidates.length));
  if (!candidates.length) {
    container.innerHTML = `<div class="empty">还没有候选项目。运行 autopilot 扫描后会自动进入队列。</div>`;
    return;
  }
  for (const candidate of candidates.slice(0, 8)) {
    const node = document.createElement("article");
    node.className = "queue-item";
    node.innerHTML = `
      <h4><a href="${candidate.url}" target="_blank" rel="noreferrer">${candidate.repo}${candidate.issue}</a></h4>
      <div class="meta">
        <span>${verdictMap[candidate.verdict] || "候选"}</span>
        <span>评分 ${candidate.score ?? "-"}</span>
        <span>${candidate.amount || ""}</span>
      </div>
      <div class="meta">${candidate.title || ""}</div>
    `;
    container.appendChild(node);
  }
}

function renderActivity(activity) {
  const container = byId("activityList");
  container.innerHTML = "";
  setText("activityCount", `${activity.length} events`);
  if (!activity.length) {
    container.innerHTML = `<div class="empty">还没有记录到活动。</div>`;
    return;
  }
  for (const event of activity.slice(0, 30)) {
    const node = document.createElement("article");
    node.className = "activity-item";
    node.innerHTML = `
      <div class="activity-time">${event.time || "-"}</div>
      <div>
        <p>${event.message || ""}</p>
        <div class="meta"><span>${event.level || "info"}</span></div>
      </div>
    `;
    container.appendChild(node);
  }
}

function render(state) {
  const earnings = state.earnings || {};
  const progress = state.progress || {};
  const wallet = state.wallet || {};
  const rate = Number(earnings.estimated_usd_per_rtc || 0.1);
  const received = Number(earnings.received_rtc || 0);
  const approvedMin = Number(earnings.approved_pending_min_rtc || 0);
  const approvedMax = Number(earnings.approved_pending_max_rtc || approvedMin);
  const submittedMin = Number(earnings.submitted_pending_min_rtc || 0);
  const submittedMax = Number(earnings.submitted_pending_max_rtc || submittedMin);
  const pipelineMin = received + approvedMin + submittedMin;
  const pipelineMax = received + approvedMax + submittedMax;

  setText("updatedAt", state.updated_at || "-");
  setText("receivedRtc", `${received.toFixed(2)} RTC`);
  setText("receivedUsd", `约 $${money.format(received * rate)}`);
  setText("approvedRtc", rtc(approvedMin, approvedMax));
  setText("submittedRtc", rtc(submittedMin, submittedMax));
  setText("pipelineRtc", rtc(pipelineMin, pipelineMax));
  setText("pipelineUsd", `潜在约 $${money.format(pipelineMin * rate)}-${money.format(pipelineMax * rate)}`);
  setText("modePill", state.mode || "manual_confirm");
  setText("walletPill", `${received.toFixed(2)} RTC`);
  setText("walletId", wallet.wallet_id || "-");
  setText("walletChecked", wallet.last_checked_at || "-");
  setText("progressActive", progress.active || 0);
  setText("progressApproved", progress.approved || 0);
  setText("progressSubmitted", progress.submitted || 0);
  setText("progressNeedsChanges", progress.needs_changes || 0);
  setText("progressMerged", progress.merged || 0);
  setText("progressRejected", progress.rejected || 0);
  setText("nextAction", state.next_action || "-");

  const ok = state.health ? state.health.ok !== false : true;
  byId("healthDot").className = `status-dot ${ok ? "ok" : "bad"}`;
  setText("healthText", ok ? "系统正常" : "需要处理");

  renderActiveItems(state.active_items || []);
  renderQueue(state.candidate_queue || []);
  renderActivity(state.activity || []);
}

async function loadState() {
  const button = byId("refreshBtn");
  button.disabled = true;
  try {
    const response = await fetch("/api/state", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    render(await response.json());
  } catch (error) {
    byId("healthDot").className = "status-dot bad";
    setText("healthText", `面板错误：${error.message}`);
  } finally {
    button.disabled = false;
  }
}

byId("refreshBtn").addEventListener("click", loadState);
loadState();
setInterval(loadState, 30000);
