"use strict";
const $ = (id) => document.getElementById(id);
const fmt = new Intl.NumberFormat();
let snapshot = null,
  token = null,
  editTarget = null,
  historyCar = null,
  cursor = null;
let lastRuntimeAt = null;
// Page-session history, independent of snapshot replacement and CV run identity.
const incidents = [],
  incidentLimit = 20,
  remoteReports = new Map();
const communicationMessages = {
  http: "Overview refresh unavailable",
  websocket: "Live updates unavailable",
  redis: "Counting status unavailable",
  updates: "Updates interrupted",
};
const runtimeMessages = {
  camera: "Camera signal interrupted",
  processing: "Bag processing interrupted",
  persistence: "A bag count could not be saved",
  startup: "Counting model could not start",
};
let socket = null,
  reconnect = null,
  sequence = 0,
  receivedAt = 0,
  polling = false,
  stopped = false;
const text = (id, value) => {
  $(id).textContent = value;
};
const localTime = (value) =>
  value
    ? new Date(value).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      })
    : "—";
function tick() {
  const now = new Date();
  text(
    "clock",
    now.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }),
  );
  text(
    "date",
    now.toLocaleDateString([], {
      day: "numeric",
      month: "short",
      year: "numeric",
    }),
  );
  if (receivedAt && performance.now() - receivedAt > 12000) {
    communication("updates", true);
  }
}
async function request(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    signal: AbortSignal.timeout(8000),
  });
  const data = await response.json();
  if (!response.ok) {
    const error = new Error("Request failed");
    error.status = response.status;
    error.data = data;
    throw error;
  }
  return data;
}
function recordIncident(key, active, details = {}) {
  const now = new Date().toISOString();
  let item = incidents.find((entry) => entry.key === key && entry.active);
  if (!item) {
    if (!active && !details.first_at) return;
    if (incidents.length >= incidentLimit) {
      const recovered = incidents.findIndex((entry) => !entry.active);
      incidents.splice(recovered < 0 ? 0 : recovered, 1);
    }
    item = { key, first_at: details.first_at || now, count: 0 };
    incidents.push(item);
  }
  Object.assign(item, {
    source: details.source || item.source,
    code: details.code || item.code,
    message: details.message || item.message,
    severity: details.severity || item.severity || "warning",
    active,
    last_at: details.last_at || now,
    count: details.count ?? item.count + (active ? 1 : 0),
    recovered_at: active ? null : details.last_at || now,
  });
}
function communication(code, active) {
  recordIncident(`communication:${code}`, active, {
    source: "Communication",
    code,
    message: communicationMessages[code],
  });
  connectionStatus();
  alerts();
}
function connectionStatus() {
  const interrupted = incidents.some(
    (a) => a.active && a.source === "Communication",
  );
  const fresh = receivedAt && performance.now() - receivedAt <= 12000;
  text(
    "connection",
    fresh
      ? interrupted
        ? "Connection interrupted · using refreshed data"
        : "Live overview"
      : "Updates interrupted · data may be stale",
  );
  if (fresh) return;
  text("status", "Status unavailable");
  $("status").className = "badge muted";
  text(
    "status-reason",
    "Connection interrupted. Last saved values are retained.",
  );
  for (const part of ["camera", "detector", "tracker"]) {
    text(`${part}-status`, "Unknown");
    $(`${part}-status`).className = "state muted";
  }
}

function runtimeIncidents() {
  const live = snapshot.runtime,
    status = live.status;
  recordIncident("communication:redis", status.state === "unavailable", {
    source: "Communication",
    code: "redis",
    message: communicationMessages.redis,
  });
  // An unavailable bridge cannot establish recovery of a counting-system fault.
  if (status.state !== "unavailable") {
    const reports = new Map(
      (live.data?.alerts || [])
        .filter((a) => Object.hasOwn(runtimeMessages, a.code))
        .map((a) => [a.code, a]),
    );
    for (const code of Object.keys(runtimeMessages)) {
      const report = reports.get(code),
        key = `counting:${code}`;
      // Expired telemetry establishes a stopped reporter, not recovery of its
      // camera or write fault. Wait for evidence from that dependency.
      if (!live.data && code !== "processing") continue;
      if (code === "camera" && status.camera === "Unknown" && !report) continue;
      const derived =
        code === "camera"
          ? status.camera === "Unavailable"
          : code === "processing" &&
            status.state === "offline" &&
            !reports.get("startup")?.active;
      const active = !!(report?.active || derived);
      const signature = JSON.stringify([live.data?.run_id, report, active]);
      if (remoteReports.get(code) === signature) continue;
      remoteReports.set(code, signature);
      const current = incidents.find((a) => a.key === key && a.active);
      // Runtime counts are cumulative; repeated snapshots are not occurrences.
      recordIncident(key, active, {
        source: "Counting system",
        code,
        message: runtimeMessages[code],
        severity: code === "camera" ? "warning" : "error",
        first_at: report?.first_at || (report ? report.last_at : undefined),
        last_at: active && !report?.active ? undefined : report?.last_at,
        count: Math.max(current?.count || 1, report?.count || 1),
      });
    }
  }
  const context = snapshot.context_error;
  recordIncident("loading:context", !!context, {
    source: "Loading",
    code: "context",
    message:
      context === "no_active_car"
        ? "No active car"
        : "Active car needs attention",
  });
}
function rows(target, events, carNumber, append = false) {
  const body = $(target);
  if (!append) body.replaceChildren();
  if (!events.length && !append) {
    const tr = body.insertRow();
    const cell = tr.insertCell();
    cell.colSpan = 4;
    cell.className = "empty";
    cell.textContent = "No saved counts yet";
    return;
  }
  for (const event of events) {
    if (body.querySelector(`[data-event="${Number(event.id)}"]`)) continue;
    const tr = body.insertRow();
    tr.dataset.event = event.id;
    const cls =
      event.class === "empty"
        ? "Empty"
        : event.class === "unknown"
          ? "Unknown"
          : event.class;
    for (const value of [
      localTime(event.counted_at),
      cls,
      carNumber,
      "✓ Count saved",
    ])
      tr.insertCell().textContent = value;
    tr.lastChild.className = "result";
  }
}
function drawChart(series) {
  const buckets = series?.buckets || [],
    svgNS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(svgNS, "svg");
  svg.setAttribute("viewBox", "0 0 400 230");
  const el = (name, attrs, content) => {
    const node = document.createElementNS(svgNS, name);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    if (content !== undefined) node.textContent = content;
    svg.append(node);
    return node;
  };
  const max = Math.max(4, ...buckets.map((b) => b.count)),
    top = 12,
    bottom = 195,
    left = 30,
    width = 360;
  for (let i = 0; i <= 4; i++) {
    const y = bottom - ((bottom - top) * i) / 4;
    el("line", {
      x1: left,
      y1: y,
      x2: 390,
      y2: y,
      stroke: "#e8eee7",
      "stroke-dasharray": "3 4",
    });
    el(
      "text",
      {
        x: 20,
        y: y + 4,
        "text-anchor": "end",
        fill: "#859087",
        "font-size": 10,
      },
      String(Math.round((max * i) / 4)),
    );
  }
  buckets.forEach((b, i) => {
    const slot = width / Math.max(1, buckets.length),
      h = (b.count / max) * (bottom - top);
    const bar = el("rect", {
      x: left + i * slot + 2,
      y: bottom - h,
      width: Math.max(1, slot - 4),
      height: Math.max(1, h),
      rx: 2,
      fill: b.count ? "#4d8c77" : "#e4ece4",
    });
    const title = document.createElementNS(svgNS, "title");
    title.textContent = `${localTime(b.at)} · ${b.count} bags`;
    bar.append(title);
  });
  if (buckets.length)
    for (const i of [
      ...new Set([0, Math.floor(buckets.length / 2), buckets.length - 1]),
    ])
      el(
        "text",
        {
          x: left + (width * i) / (buckets.length - 1 || 1),
          y: 220,
          "text-anchor":
            i === 0 ? "start" : i === buckets.length - 1 ? "end" : "middle",
          fill: "#859087",
          "font-size": 10,
        },
        new Date(buckets[i].at).toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        }),
      );
  if (!buckets.length)
    el(
      "text",
      {
        x: 210,
        y: 105,
        "text-anchor": "middle",
        fill: "#859087",
        "font-size": 12,
      },
      "No count history available",
    );
  $("chart").replaceChildren(svg);
  const total = buckets.reduce((n, b) => n + b.count, 0);
  $("chart").setAttribute(
    "aria-label",
    `${total} saved bags in displayed interval`,
  );
  text("chart-total", `${fmt.format(total)} bags in this interval`);
}
function alerts() {
  const active = incidents
    .filter((a) => a.active)
    .sort(
      (a, b) => Number(b.severity === "error") - Number(a.severity === "error"),
    );
  let title = "No active warnings",
    detail = "Counting system messages appear here.",
    kind = "";
  if (active.length) {
    title = active[0].message;
    detail = `${localTime(active[0].last_at)} · ${active[0].count} occurrence${active[0].count === 1 ? "" : "s"}`;
    kind = active[0].severity;
  }
  text("alert-title", title);
  text("alert-detail", detail);
  text("alert-icon", kind ? "!" : "✓");
  document.querySelector(".alert-strip").className = `alert-strip ${kind}`;
  const list = $("alert-list");
  list.replaceChildren();
  const items = [...incidents].reverse();
  if (!items.length) {
    const p = document.createElement("p");
    p.textContent = title;
    list.append(p);
  }
  for (const a of items) {
    const div = document.createElement("div");
    div.className = "alert-entry";
    div.dataset.incident = a.key;
    div.dataset.active = String(a.active);
    const strong = document.createElement("strong");
    strong.textContent = a.message;
    const p = document.createElement("p");
    p.className = "subtle";
    p.textContent = `${a.active ? "Active" : "Recovered"} · ${a.severity} · ${a.source} · ${a.count} occurrences`;
    const times = document.createElement("p");
    times.className = "subtle";
    // Include the date so an overnight outage remains unambiguous.
    const when = (value) => new Date(value).toLocaleString();
    times.textContent = `First ${when(a.first_at)} · Last ${when(a.last_at)}${a.recovered_at ? ` · Recovered ${when(a.recovered_at)}` : ""}`;
    div.append(strong, p, times);
    list.append(div);
  }
}
function render(data) {
  // Suppress briefly reordered reads; a corrected server clock must not freeze counts.
  if (
    snapshot &&
    Date.parse(data.database_at) < Date.parse(snapshot.database_at) &&
    performance.now() - receivedAt < 5000
  )
    return;
  snapshot = data;
  receivedAt = performance.now();
  recordIncident("communication:updates", false);
  const car = data.car,
    totals = data.totals,
    status = data.runtime.status;
  text("car-number", car?.number || "No active car");
  $("edit-car").disabled = !car;
  $("history").disabled = !car;
  text("count", car ? fmt.format(totals.total) : "—");
  text(
    "count-context",
    car
      ? "Successfully saved for this loading session"
      : "No single active car",
  );
  text("class-25", car ? fmt.format(totals.by_class["25kg"]) : "—");
  text("class-50", car ? fmt.format(totals.by_class["50kg"]) : "—");
  text("class-empty", car ? fmt.format(totals.by_class.empty) : "—");
  text("weight", car ? `${fmt.format(totals.weight_kg)} kg` : "—");
  text("status", status.label);
  $("status").className =
    `badge ${["online", "offline", "starting"].includes(status.state) ? status.state : "muted"}`;
  if (status.updated_at) lastRuntimeAt = status.updated_at;
  text(
    "status-reason",
    `${status.reason}${lastRuntimeAt ? ` · Last report ${localTime(lastRuntimeAt)}` : ""}`,
  );
  for (const part of ["camera", "detector", "tracker"]) {
    text(`${part}-status`, status[part]);
    $(`${part}-status`).className =
      `state ${["Connected", "Running"].includes(status[part]) ? "online" : status[part] === "Unknown" ? "muted" : "starting"}`;
  }
  const last = data.runtime.data?.last_detection;
  text("detection-time", localTime(last?.observed_at));
  text(
    "detection-class",
    last
      ? last.class === "empty"
        ? "Empty"
        : last.class || "Unknown"
      : "No detection yet",
  );
  text(
    "detection-state",
    last
      ? last.track_id == null
        ? "Unconfirmed"
        : last.state
      : "Waiting for a bag",
  );
  const image = last?.thumbnail;
  const validImage =
    typeof image === "string" && image.startsWith("data:image/jpeg;base64,");
  $("thumbnail").hidden = !validImage;
  $("thumbnail-empty").hidden = validImage;
  if (validImage) $("thumbnail").src = image;
  rows("events", data.recent.events, car?.number || "—");
  drawChart(data.series);
  runtimeIncidents();
  connectionStatus();
  alerts();
  text("updated", `Saved data updated ${localTime(data.database_at)}`);
}
async function poll() {
  if (polling || stopped) return;
  polling = true;
  try {
    const data = await request("/api/v1/dashboard/snapshot");
    communication("http", false);
    render(data);
  } catch {
    communication("http", true);
  } finally {
    polling = false;
  }
}
function connect() {
  if (stopped) return;
  socket = new WebSocket(
    `${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}/api/v1/dashboard/live`,
  );
  sequence = 0;
  socket.onmessage = (event) => {
    try {
      const message = JSON.parse(event.data);
      if (message.sequence <= sequence) return;
      sequence = message.sequence;
      if (message.type === "snapshot") {
        communication("websocket", false);
        render(message.data);
      } else communication("websocket", true);
    } catch {
      communication("websocket", true);
    }
  };
  socket.onclose = () => {
    if (stopped) return;
    communication("websocket", true);
    poll();
    reconnect = setTimeout(connect, 3000);
  };
  socket.onerror = () => socket.close();
}
$("edit-car").onclick = () => {
  editTarget = { ...snapshot.car };
  $("car-input").value = editTarget.number;
  text("car-error", "");
  $("login-fields").hidden = !!token;
  $("car-dialog").showModal();
  $("car-input").focus();
};
for (const button of document.querySelectorAll(".close-dialog"))
  button.onclick = () => button.closest("dialog").close();
$("car-form").onsubmit = async (event) => {
  event.preventDefault();
  text("car-error", "");
  $("save-car").disabled = true;
  try {
    if (!token) {
      const credentials = new URLSearchParams({
        username: $("username").value,
        password: $("password").value,
      });
      const login = await request("/api/v1/auth/login", {
        method: "POST",
        body: credentials,
      });
      token = login.access_token;
      $("password").value = "";
      $("login-fields").hidden = true;
    }
    const current = await request(`/api/v1/wagons/${editTarget.id}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        number: $("car-input").value,
        revision: editTarget.revision,
      }),
    });
    editTarget = current;
    $("car-dialog").close();
    await poll();
  } catch (error) {
    if (error.status === 401) {
      token = null;
      $("password").value = "";
      $("login-fields").hidden = false;
      text("car-error", "Please log in with valid operator credentials.");
    } else if (error.status === 409) {
      const current = error.data.detail?.current;
      if (current?.id === editTarget.id) editTarget = current;
      text(
        "car-error",
        `Car information changed${current ? ` (current number: ${current.number})` : ""}. Your entry is retained. Review before saving again.`,
      );
    } else if (error.status === 422)
      text("car-error", "Enter a car number of 1 to 32 characters.");
    else if (error.status === 429)
      text("car-error", "Too many login attempts. Try again in a minute.");
    else
      text(
        "car-error",
        "Could not confirm the save. Your entry is retained. Reconnect and review the current number before retrying.",
      );
  } finally {
    $("save-car").disabled = false;
  }
};
async function loadHistory(append = false) {
  $("more-history").disabled = true;
  text("history-error", "");
  try {
    const page = await request(
      `/api/v1/events?car_id=${historyCar.id}&limit=25${append && cursor ? `&before=${cursor}` : ""}`,
    );
    rows("history-events", page.events, historyCar.number, append);
    cursor = page.next_cursor;
    $("more-history").hidden = !cursor;
  } catch {
    text("history-error", "History is temporarily unavailable. Try again.");
  } finally {
    $("more-history").disabled = false;
  }
}
$("history").onclick = () => {
  historyCar = { ...snapshot.car };
  cursor = null;
  text("history-context", `Car ${historyCar.number} · saved counts`);
  $("history-dialog").showModal();
  loadHistory();
};
$("more-history").onclick = () => loadHistory(true);
$("show-alerts").onclick = () => $("alerts-dialog").showModal();
$("start-video").onclick = () => {
  $("video-placeholder").hidden = true;
  $("video").hidden = false;
  $("preview-label").hidden = false;
  $("video").src = "/api/v1/video/stream";
};
$("video").onerror = () => {
  $("video").hidden = true;
  $("preview-label").hidden = true;
  $("video-placeholder").hidden = false;
  $("video-placeholder").querySelector("strong").textContent =
    "Camera preview unavailable";
  $("start-video").textContent = "Try again";
};
$("expand-video").onclick = () => {
  if (document.fullscreenElement) document.exitFullscreen();
  else
    $("video-container")
      .requestFullscreen?.()
      .catch(() => {});
};
const clockTimer = setInterval(tick, 1000),
  pollTimer = setInterval(poll, 5000);
tick();
poll();
connect();
window.addEventListener("pagehide", () => {
  stopped = true;
  clearInterval(clockTimer);
  clearInterval(pollTimer);
  clearTimeout(reconnect);
  socket?.close();
  $("video").removeAttribute("src");
});
