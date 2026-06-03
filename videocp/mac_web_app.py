from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from videocp.mac_scheduler import default_app_config_path, ensure_app_config, save_app_config_file, write_tasks_file

HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Videocp Scheduler</title>
  <style>
    :root { color-scheme: light; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    body { margin: 0; background: #f6f7f8; color: #182026; }
    header { padding: 18px 24px; background: #ffffff; border-bottom: 1px solid #d8dde3; display: flex; align-items: center; justify-content: space-between; }
    h1 { margin: 0; font-size: 20px; font-weight: 700; }
    main { padding: 20px 24px 28px; display: grid; gap: 16px; }
    section { background: #fff; border: 1px solid #d8dde3; border-radius: 8px; padding: 16px; }
    h2 { margin: 0 0 14px; font-size: 15px; }
    label { display: grid; gap: 6px; font-size: 12px; color: #48525c; font-weight: 600; }
    input, select, textarea { font: inherit; border: 1px solid #c7ced6; border-radius: 6px; padding: 8px 9px; background: #fff; box-sizing: border-box; width: 100%; }
    textarea { min-height: 72px; resize: vertical; }
    .grid { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 12px; align-items: end; }
    .grid .span2 { grid-column: span 2; }
    .grid .span3 { grid-column: span 3; }
    .grid .span6 { grid-column: span 6; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { border-bottom: 1px solid #e5e8eb; padding: 9px 8px; text-align: left; vertical-align: top; }
    th { color: #5b6670; font-weight: 700; }
    tr.selected { background: #eaf4ff; }
    button { border: 1px solid #aab4bf; border-radius: 6px; background: #fff; padding: 8px 12px; font: inherit; cursor: pointer; }
    button.primary { background: #1264a3; border-color: #1264a3; color: #fff; }
    button.danger { color: #b42318; border-color: #e6b8b3; }
    .actions { display: flex; gap: 8px; flex-wrap: wrap; }
    .status { font-size: 13px; color: #48525c; }
    pre { margin: 0; background: #111820; color: #dce7f2; border-radius: 8px; padding: 12px; min-height: 180px; max-height: 260px; overflow: auto; font-size: 12px; line-height: 1.45; }
    @media (max-width: 900px) { .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } .grid .span2, .grid .span3, .grid .span6 { grid-column: span 2; } }
  </style>
</head>
<body>
  <header>
    <h1>Videocp Scheduler</h1>
    <div class="status" id="status">加载中</div>
  </header>
  <main>
    <section>
      <h2>调度与清理</h2>
      <div class="grid">
        <label>每天开始 <input id="active_start" placeholder="09:00"></label>
        <label>每天结束 <input id="active_end" placeholder="23:00"></label>
        <label>间隔分钟 <input id="run_interval_minutes" type="number" min="1"></label>
        <label>每主页条数 <input id="videos_per_task" type="number" min="1"></label>
        <label>保留天数 <input id="max_age_days" type="number" min="0"></label>
        <label>磁盘上限 GB <input id="max_total_gb" type="number" min="0" step="0.5"></label>
      </div>
    </section>
    <section>
      <h2>来源主页</h2>
      <table>
        <thead><tr><th>名称</th><th>主页 URL</th><th>范围</th><th>频道ID</th><th>版块ID</th><th>条数</th></tr></thead>
        <tbody id="sources"></tbody>
      </table>
    </section>
    <section>
      <h2>编辑来源</h2>
      <div class="grid">
        <label class="span2">名称 <input id="name"></label>
        <label class="span3">主页 URL <input id="source_url"></label>
        <label>条数 <input id="count" type="number" min="1" value="1"></label>
        <label>发帖范围 <select id="publish_scope"><option value="author_global">创作者全局贴</option><option value="channel">频道内发帖</option></select></label>
        <label class="span2">频道ID <input id="guild_id"></label>
        <label class="span2">版块ID <input id="channel_id"></label>
        <label class="span3">标题模板 <input id="title_template" value="{title}"></label>
        <label class="span3">正文模板 <input id="content_template" value="{title}"></label>
      </div>
      <div class="actions" style="margin-top:12px">
        <button class="primary" onclick="upsertSource()">新增/更新来源</button>
        <button class="danger" onclick="deleteSource()">删除来源</button>
        <button onclick="clearEditor()">清空编辑区</button>
      </div>
    </section>
    <section>
      <h2>操作</h2>
      <div class="actions">
        <button class="primary" onclick="saveConfig()">保存配置</button>
        <button onclick="runOnce()">运行一次</button>
        <button onclick="startScheduler()">启动定时</button>
        <button onclick="stopScheduler()">停止定时</button>
      </div>
    </section>
    <section>
      <h2>日志</h2>
      <pre id="logs"></pre>
    </section>
  </main>
<script>
let config = null;
let selected = -1;

async function api(path, options = {}) {
  const res = await fetch(path, options);
  const text = await res.text();
  let data = {};
  try { data = text ? JSON.parse(text) : {}; } catch { data = {ok:false, error:text}; }
  if (!res.ok) throw new Error(data.error || text || res.statusText);
  return data;
}

function setStatus(text) { document.getElementById('status').textContent = text; }
function val(id) { return document.getElementById(id).value.trim(); }
function setVal(id, value) { document.getElementById(id).value = value ?? ''; }

async function loadConfig() {
  config = await api('/config');
  setVal('active_start', config.active_start || '09:00');
  setVal('active_end', config.active_end || '23:00');
  setVal('run_interval_minutes', config.run_interval_minutes || 60);
  setVal('videos_per_task', config.sync?.videos_per_task || 1);
  setVal('max_age_days', config.cleanup?.max_age_days ?? 7);
  setVal('max_total_gb', config.cleanup?.max_total_gb ?? 20);
  renderSources();
  setStatus(config.config_path || '已加载');
}

function captureConfig() {
  config.active_start = val('active_start') || '09:00';
  config.active_end = val('active_end') || '23:00';
  config.run_interval_minutes = Number(val('run_interval_minutes') || 60);
  config.sync = config.sync || {};
  config.sync.videos_per_task = Number(val('videos_per_task') || 1);
  config.cleanup = config.cleanup || {};
  config.cleanup.enabled = true;
  config.cleanup.max_age_days = Number(val('max_age_days') || 0);
  config.cleanup.max_total_gb = Number(val('max_total_gb') || 0);
}

function renderSources() {
  const body = document.getElementById('sources');
  body.innerHTML = '';
  (config.sources || []).forEach((s, i) => {
    const tr = document.createElement('tr');
    if (i === selected) tr.className = 'selected';
    tr.onclick = () => selectSource(i);
    tr.innerHTML = `<td>${escapeHtml(s.name || '')}</td><td>${escapeHtml(s.source_url || '')}</td><td>${s.publish_scope === 'channel' ? '频道内' : '全局'}</td><td>${escapeHtml(s.guild_id || '')}</td><td>${escapeHtml(s.channel_id || '')}</td><td>${escapeHtml(String(s.count || ''))}</td>`;
    body.appendChild(tr);
  });
}

function selectSource(i) {
  selected = i;
  const s = config.sources[i];
  setVal('name', s.name || '');
  setVal('source_url', s.source_url || '');
  setVal('publish_scope', s.publish_scope || 'author_global');
  setVal('guild_id', s.guild_id || '');
  setVal('channel_id', s.channel_id || '');
  setVal('count', s.count || 1);
  setVal('title_template', s.title_template || '{title}');
  setVal('content_template', s.content_template || '{title}');
  renderSources();
}

function editorSource() {
  const source = {
    enabled: true,
    name: val('name') || val('source_url'),
    source_url: val('source_url'),
    publish_scope: val('publish_scope') || 'author_global',
    guild_id: val('guild_id'),
    channel_id: val('channel_id'),
    count: Number(val('count') || 1),
    title_template: val('title_template') || '{title}',
    content_template: val('content_template') || '{title}',
    feed_type: 1
  };
  if (!source.source_url) throw new Error('请填写主页 URL');
  if (source.publish_scope === 'channel' && (!source.guild_id || !source.channel_id)) throw new Error('频道内发帖需要频道ID和版块ID');
  return source;
}

function upsertSource() {
  try {
    config.sources = config.sources || [];
    const source = editorSource();
    if (selected >= 0) config.sources[selected] = source;
    else { config.sources.push(source); selected = config.sources.length - 1; }
    renderSources();
  } catch (e) { alert(e.message); }
}

function deleteSource() {
  if (selected < 0) return;
  config.sources.splice(selected, 1);
  selected = -1;
  clearEditor();
  renderSources();
}

function clearEditor() {
  selected = -1;
  ['name','source_url','guild_id','channel_id'].forEach(id => setVal(id, ''));
  setVal('publish_scope', 'author_global');
  setVal('count', 1);
  setVal('title_template', '{title}');
  setVal('content_template', '{title}');
  renderSources();
}

async function saveConfig() {
  captureConfig();
  await api('/config', {method:'POST', body: JSON.stringify(config)});
  setStatus('已保存');
}

async function runOnce() { await saveConfig(); await api('/run-once', {method:'POST'}); }
async function startScheduler() { await saveConfig(); await api('/start', {method:'POST'}); }
async function stopScheduler() { await api('/stop', {method:'POST'}); }

async function refreshLogs() {
  const data = await api('/logs');
  document.getElementById('logs').textContent = (data.logs || []).join('\\n');
  setTimeout(refreshLogs, 1000);
}

function escapeHtml(text) {
  return text.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

loadConfig().catch(e => alert(e.message));
refreshLogs().catch(() => setTimeout(refreshLogs, 1000));
</script>
</body>
</html>
"""


class AppState:
    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.logs: list[str] = []
        self.lock = threading.Lock()
        self.scheduler_proc: subprocess.Popen[str] | None = None

    def log(self, message: str) -> None:
        with self.lock:
            self.logs.append(message)
            self.logs = self.logs[-300:]


class Handler(BaseHTTPRequestHandler):
    state: AppState

    def log_message(self, format: str, *args) -> None:
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_html(HTML)
            return
        if parsed.path == "/config":
            config = ensure_app_config(self.state.config_path)
            config["config_path"] = str(self.state.config_path)
            self._send_json(config)
            return
        if parsed.path == "/logs":
            with self.state.lock:
                logs = list(self.state.logs)
            self._send_json({"logs": logs})
            return
        self.send_error(404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/config":
                payload = self._read_json()
                payload.pop("config_path", None)
                save_app_config_file(self.state.config_path, payload)
                tasks_path = write_tasks_file(payload, self.state.config_path)
                self.state.log(f"已保存配置，并生成 {tasks_path}")
                self._send_json({"ok": True})
                return
            if parsed.path == "/run-once":
                self._start_one_shot()
                self._send_json({"ok": True})
                return
            if parsed.path == "/start":
                self._start_scheduler()
                self._send_json({"ok": True})
                return
            if parsed.path == "/stop":
                self._stop_scheduler()
                self._send_json({"ok": True})
                return
            self.send_error(404)
        except Exception as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=500)

    def _start_one_shot(self) -> None:
        command = [sys.executable, "-m", "videocp.mac_scheduler", "--app-config", str(self.state.config_path), "--once"]
        self.state.log("开始运行一次")
        threading.Thread(target=self._run_and_log, args=(command,), daemon=True).start()

    def _start_scheduler(self) -> None:
        if self.state.scheduler_proc is not None and self.state.scheduler_proc.poll() is None:
            self.state.log("定时器已经在运行")
            return
        command = [sys.executable, "-m", "videocp.mac_scheduler", "--app-config", str(self.state.config_path)]
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.state.scheduler_proc = proc
        self.state.log("定时器已启动")
        threading.Thread(target=self._stream_proc, args=(proc,), daemon=True).start()

    def _stop_scheduler(self) -> None:
        proc = self.state.scheduler_proc
        if proc is not None and proc.poll() is None:
            proc.terminate()
            self.state.log("定时器已停止")
        self.state.scheduler_proc = None

    def _run_and_log(self, command: list[str]) -> None:
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self._stream_proc(proc)

    def _stream_proc(self, proc: subprocess.Popen[str]) -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            self.state.log(line.rstrip())
        proc.wait()
        self.state.log(f"命令结束，退出码 {proc.returncode}")

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw or "{}")

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="videocp mac-app")
    parser.add_argument("--app-config", default=str(default_app_config_path()))
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args(argv)

    config_path = Path(args.app_config).expanduser().resolve()
    ensure_app_config(config_path)
    port = args.port or find_free_port()
    state = AppState(config_path)
    Handler.state = state
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    state.log(f"控制台已启动: {url}")
    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if state.scheduler_proc is not None and state.scheduler_proc.poll() is None:
            state.scheduler_proc.terminate()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
