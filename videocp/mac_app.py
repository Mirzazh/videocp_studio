from __future__ import annotations

import queue
import subprocess
import sys
import threading
import tkinter as tk
import argparse
from pathlib import Path
from tkinter import messagebox, ttk

from videocp.mac_scheduler import (
    default_app_config_path,
    ensure_app_config,
    save_app_config_file,
    write_tasks_file,
)


class VideoCpMacApp:
    def __init__(self, root: tk.Tk, config_path: Path):
        self.root = root
        self.config_path = config_path
        self.config = ensure_app_config(config_path)
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.scheduler_proc: subprocess.Popen[str] | None = None

        self.root.title("videocp 定时发帖")
        self.root.geometry("980x680")
        self._build()
        self._load_config_to_ui()
        self._poll_log_queue()

    def _build(self) -> None:
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)

        schedule = ttk.LabelFrame(outer, text="调度窗口", padding=10)
        schedule.pack(fill="x")
        self.start_var = tk.StringVar()
        self.end_var = tk.StringVar()
        self.interval_var = tk.StringVar()
        self.videos_per_task_var = tk.StringVar()
        self.cleanup_days_var = tk.StringVar()
        self.cleanup_gb_var = tk.StringVar()

        self._grid_label_entry(schedule, "每天开始", self.start_var, 0, 0, width=10)
        self._grid_label_entry(schedule, "每天结束", self.end_var, 0, 2, width=10)
        self._grid_label_entry(schedule, "间隔分钟", self.interval_var, 0, 4, width=10)
        self._grid_label_entry(schedule, "每主页条数", self.videos_per_task_var, 1, 0, width=10)
        self._grid_label_entry(schedule, "保留天数", self.cleanup_days_var, 1, 2, width=10)
        self._grid_label_entry(schedule, "磁盘上限GB", self.cleanup_gb_var, 1, 4, width=10)

        source_frame = ttk.LabelFrame(outer, text="来源主页", padding=10)
        source_frame.pack(fill="both", expand=True, pady=(12, 0))

        columns = ("name", "url", "scope", "guild", "channel", "count")
        self.source_tree = ttk.Treeview(source_frame, columns=columns, show="headings", height=10)
        headings = {
            "name": "名称",
            "url": "主页 URL",
            "scope": "发帖范围",
            "guild": "频道ID",
            "channel": "版块ID",
            "count": "条数",
        }
        widths = {"name": 160, "url": 360, "scope": 100, "guild": 120, "channel": 120, "count": 60}
        for column in columns:
            self.source_tree.heading(column, text=headings[column])
            self.source_tree.column(column, width=widths[column], anchor="w")
        self.source_tree.pack(side="left", fill="both", expand=True)
        self.source_tree.bind("<<TreeviewSelect>>", lambda _event: self._load_selected_source())
        scrollbar = ttk.Scrollbar(source_frame, orient="vertical", command=self.source_tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.source_tree.configure(yscrollcommand=scrollbar.set)

        editor = ttk.LabelFrame(outer, text="编辑来源", padding=10)
        editor.pack(fill="x", pady=(12, 0))
        self.name_var = tk.StringVar()
        self.url_var = tk.StringVar()
        self.scope_var = tk.StringVar(value="author_global")
        self.guild_var = tk.StringVar()
        self.channel_var = tk.StringVar()
        self.count_var = tk.StringVar(value="1")
        self.title_template_var = tk.StringVar(value="{title}")
        self.content_template_var = tk.StringVar(value="{title}")

        self._grid_label_entry(editor, "名称", self.name_var, 0, 0, width=22)
        self._grid_label_entry(editor, "主页URL", self.url_var, 0, 2, width=54)
        ttk.Label(editor, text="范围").grid(row=1, column=0, sticky="e", padx=(0, 6), pady=5)
        ttk.Combobox(
            editor,
            textvariable=self.scope_var,
            values=("author_global", "channel"),
            width=18,
            state="readonly",
        ).grid(row=1, column=1, sticky="w", pady=5)
        self._grid_label_entry(editor, "频道ID", self.guild_var, 1, 2, width=24)
        self._grid_label_entry(editor, "版块ID", self.channel_var, 1, 4, width=24)
        self._grid_label_entry(editor, "条数", self.count_var, 2, 0, width=8)
        self._grid_label_entry(editor, "标题模板", self.title_template_var, 2, 2, width=28)
        self._grid_label_entry(editor, "正文模板", self.content_template_var, 2, 4, width=28)

        button_row = ttk.Frame(outer)
        button_row.pack(fill="x", pady=(12, 0))
        ttk.Button(button_row, text="新增/更新来源", command=self._upsert_source).pack(side="left")
        ttk.Button(button_row, text="删除来源", command=self._delete_source).pack(side="left", padx=(8, 0))
        ttk.Button(button_row, text="保存配置", command=self._save).pack(side="left", padx=(18, 0))
        ttk.Button(button_row, text="运行一次", command=self._run_once).pack(side="left", padx=(8, 0))
        ttk.Button(button_row, text="启动定时", command=self._start_scheduler).pack(side="left", padx=(8, 0))
        ttk.Button(button_row, text="停止定时", command=self._stop_scheduler).pack(side="left", padx=(8, 0))

        self.status_var = tk.StringVar(value=f"配置文件: {self.config_path}")
        ttk.Label(outer, textvariable=self.status_var).pack(anchor="w", pady=(10, 4))
        self.log_text = tk.Text(outer, height=9, wrap="word")
        self.log_text.pack(fill="both")

    def _grid_label_entry(self, parent, label: str, var: tk.StringVar, row: int, column: int, width: int) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=column, sticky="e", padx=(0, 6), pady=5)
        ttk.Entry(parent, textvariable=var, width=width).grid(row=row, column=column + 1, sticky="w", pady=5)

    def _load_config_to_ui(self) -> None:
        self.start_var.set(str(self.config.get("active_start", "09:00")))
        self.end_var.set(str(self.config.get("active_end", "23:00")))
        self.interval_var.set(str(self.config.get("run_interval_minutes", 60)))
        self.videos_per_task_var.set(str((self.config.get("sync") or {}).get("videos_per_task", 1)))
        cleanup = self.config.get("cleanup") or {}
        self.cleanup_days_var.set(str(cleanup.get("max_age_days", 7)))
        self.cleanup_gb_var.set(str(cleanup.get("max_total_gb", 20)))
        self._refresh_sources()

    def _refresh_sources(self) -> None:
        self.source_tree.delete(*self.source_tree.get_children())
        for index, source in enumerate(self.config.get("sources") or []):
            self.source_tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    source.get("name", ""),
                    source.get("source_url", ""),
                    source.get("publish_scope", "author_global"),
                    source.get("guild_id", ""),
                    source.get("channel_id", ""),
                    source.get("count", ""),
                ),
            )

    def _load_selected_source(self) -> None:
        selected = self.source_tree.selection()
        if not selected:
            return
        source = (self.config.get("sources") or [])[int(selected[0])]
        self.name_var.set(source.get("name", ""))
        self.url_var.set(source.get("source_url", ""))
        self.scope_var.set(source.get("publish_scope", "author_global"))
        self.guild_var.set(source.get("guild_id", ""))
        self.channel_var.set(source.get("channel_id", ""))
        self.count_var.set(str(source.get("count", 1)))
        self.title_template_var.set(source.get("title_template", "{title}"))
        self.content_template_var.set(source.get("content_template", "{title}"))

    def _capture_ui_to_config(self) -> None:
        self.config["active_start"] = self.start_var.get().strip() or "09:00"
        self.config["active_end"] = self.end_var.get().strip() or "23:00"
        self.config["run_interval_minutes"] = int(self.interval_var.get() or 60)
        self.config.setdefault("sync", {})["videos_per_task"] = int(self.videos_per_task_var.get() or 1)
        self.config.setdefault("cleanup", {})["max_age_days"] = int(self.cleanup_days_var.get() or 7)
        self.config.setdefault("cleanup", {})["max_total_gb"] = float(self.cleanup_gb_var.get() or 20)

    def _source_from_editor(self) -> dict:
        source = {
            "enabled": True,
            "name": self.name_var.get().strip() or self.url_var.get().strip(),
            "source_url": self.url_var.get().strip(),
            "publish_scope": self.scope_var.get(),
            "guild_id": self.guild_var.get().strip(),
            "channel_id": self.channel_var.get().strip(),
            "count": int(self.count_var.get() or 1),
            "title_template": self.title_template_var.get().strip() or "{title}",
            "content_template": self.content_template_var.get().strip() or "{title}",
            "feed_type": 1,
        }
        if not source["source_url"]:
            raise ValueError("请填写主页 URL。")
        if source["publish_scope"] == "channel" and (not source["guild_id"] or not source["channel_id"]):
            raise ValueError("频道内发帖需要填写频道ID和版块ID。")
        return source

    def _upsert_source(self) -> None:
        try:
            source = self._source_from_editor()
            sources = self.config.setdefault("sources", [])
            selected = self.source_tree.selection()
            if selected:
                sources[int(selected[0])] = source
            else:
                sources.append(source)
            self._refresh_sources()
        except Exception as exc:
            messagebox.showerror("配置错误", str(exc))

    def _delete_source(self) -> None:
        selected = self.source_tree.selection()
        if not selected:
            return
        del self.config.setdefault("sources", [])[int(selected[0])]
        self._refresh_sources()

    def _save(self) -> None:
        try:
            self._capture_ui_to_config()
            save_app_config_file(self.config_path, self.config)
            tasks_path = write_tasks_file(self.config, self.config_path)
            self._log(f"已保存配置，并生成 {tasks_path}")
        except Exception as exc:
            messagebox.showerror("保存失败", str(exc))

    def _run_once(self) -> None:
        self._save()
        self._run_subprocess([sys.executable, "-m", "videocp.mac_scheduler", "--app-config", str(self.config_path), "--once"])

    def _start_scheduler(self) -> None:
        self._save()
        if self.scheduler_proc and self.scheduler_proc.poll() is None:
            self._log("定时器已经在运行。")
            return
        command = [sys.executable, "-m", "videocp.mac_scheduler", "--app-config", str(self.config_path)]
        self.scheduler_proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self._log("定时器已启动。")
        threading.Thread(target=self._stream_proc, args=(self.scheduler_proc,), daemon=True).start()

    def _stop_scheduler(self) -> None:
        if self.scheduler_proc and self.scheduler_proc.poll() is None:
            self.scheduler_proc.terminate()
            self._log("定时器已停止。")
        self.scheduler_proc = None

    def _run_subprocess(self, command: list[str]) -> None:
        def worker() -> None:
            proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            self._stream_proc(proc)

        threading.Thread(target=worker, daemon=True).start()

    def _stream_proc(self, proc: subprocess.Popen[str]) -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            self.log_queue.put(line.rstrip())
        proc.wait()
        self.log_queue.put(f"命令结束，退出码 {proc.returncode}")

    def _poll_log_queue(self) -> None:
        while True:
            try:
                message = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self._log(message)
        self.root.after(300, self._poll_log_queue)

    def _log(self, message: str) -> None:
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="videocp mac-app")
    parser.add_argument("--app-config", default=str(default_app_config_path()))
    args = parser.parse_args(argv)
    root = tk.Tk()
    app = VideoCpMacApp(root, Path(args.app_config).expanduser().resolve())
    root.protocol("WM_DELETE_WINDOW", lambda: (app._stop_scheduler(), root.destroy()))
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
