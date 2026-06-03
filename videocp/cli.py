from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from videocp.app import (
    DownloadOptions,
    DoctorOptions,
    doctor,
    download_jobs,
    prepare_link_list,
)
from videocp.config import AppConfig, load_app_config
from videocp.errors import VideoCpError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="videocp")
    parser.add_argument("--config", default=None, help="Path to config.yaml.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    download_parser = subparsers.add_parser("download", help="Download videos from supported sites.")
    download_parser.add_argument("inputs", nargs="*", help="URL, short link, or share text.")
    download_parser.add_argument("--input-file", default=None, help="Text file with one URL/share text per line.")
    download_parser.add_argument("--output-dir", default=None, help="Output directory.")
    download_parser.add_argument("--profile-dir", default=None, help="Dedicated Chrome profile directory.")
    download_parser.add_argument("--browser-path", default=None, help="Chrome executable path.")
    download_headless = download_parser.add_mutually_exclusive_group()
    download_headless.add_argument("--headless", dest="headless", action="store_true", help="Run Chrome headless.")
    download_headless.add_argument(
        "--no-headless",
        dest="headless",
        action="store_false",
        help="Run Chrome with a visible window.",
    )
    download_parser.set_defaults(headless=None)
    download_parser.add_argument("--json", action="store_true", help="Print result as JSON.")
    download_parser.add_argument("--timeout-secs", type=int, default=None, help="Timeout in seconds.")
    download_parser.add_argument("--profile-videos-count", type=int, default=None, help="Number of recent videos to download from a profile page.")
    download_parser.add_argument("--profile-order", choices=["latest", "popular"], default="latest", help="Profile page ordering.")
    download_parser.add_argument("--ytdlp-extractor-args", default="", help="Extra yt-dlp --extractor-args value.")

    prepare_parser = subparsers.add_parser("prepare-list", help="Resolve inputs and write a canonical URL list.")
    prepare_parser.add_argument("inputs", nargs="*", help="URL, short link, or share text.")
    prepare_parser.add_argument("--input-file", default=None, help="Text file with one URL/share text per line.")
    prepare_parser.add_argument("--output-file", required=True, help="Output txt file path.")
    prepare_parser.add_argument("--timeout-secs", type=int, default=None, help="Timeout in seconds.")
    prepare_parser.add_argument("--json", action="store_true", help="Print result as JSON.")

    doctor_parser = subparsers.add_parser("doctor", help="Check browser, profile, CDP, and ffmpeg.")
    doctor_parser.add_argument("--profile-dir", default=None, help="Dedicated Chrome profile directory.")
    doctor_parser.add_argument("--browser-path", default=None, help="Chrome executable path.")
    doctor_headless = doctor_parser.add_mutually_exclusive_group()
    doctor_headless.add_argument("--headless", dest="headless", action="store_true", help="Run Chrome headless.")
    doctor_headless.add_argument(
        "--no-headless",
        dest="headless",
        action="store_false",
        help="Run Chrome with a visible window.",
    )
    doctor_parser.set_defaults(headless=None)
    doctor_parser.add_argument("--json", action="store_true", help="Print result as JSON.")
    doctor_parser.add_argument(
        "--keep-open",
        action="store_true",
        help="Keep the visible browser open until Enter is pressed; useful for logging in.",
    )
    doctor_parser.add_argument(
        "--login-url",
        dest="login_urls",
        action="append",
        default=[],
        help="Open this URL while --keep-open is active. Can be passed multiple times.",
    )

    sync_parser = subparsers.add_parser("sync", help="Sync latest videos to QQ channels.")
    sync_parser.add_argument("--tasks-file", default=None, help="Path to tasks.yaml.")
    sync_parser.add_argument("--dry-run", action="store_true", help="Show what would be synced without executing.")
    sync_parser.add_argument("--task-name", default=None, help="Run only the named task.")
    sync_parser.add_argument("--json", action="store_true", help="Print result as JSON.")
    sync_parser.add_argument("--count", type=int, default=None, help="Number of latest videos to sync per task.")
    sync_headless = sync_parser.add_mutually_exclusive_group()
    sync_headless.add_argument("--headless", dest="headless", action="store_true", help="Run Chrome headless.")
    sync_headless.add_argument("--no-headless", dest="headless", action="store_false", help="Run Chrome with a visible window.")
    sync_parser.set_defaults(headless=None)

    app_parser = subparsers.add_parser("mac-app", help="Open the macOS scheduler app.")
    app_parser.add_argument("--app-config", default=None, help="Path to mac-app.json.")

    schedule_parser = subparsers.add_parser("schedule", help="Run the macOS scheduler loop.")
    schedule_parser.add_argument("--app-config", default=None, help="Path to mac-app.json.")
    schedule_parser.add_argument("--once", action="store_true", help="Run one scheduled sync cycle and exit.")
    schedule_parser.add_argument("--dry-run", action="store_true", help="Plan without downloading or publishing.")
    schedule_parser.add_argument("--task-name", default=None, help="Run only the named source task.")

    app_download_parser = subparsers.add_parser("app-download", help="Run macOS app download workflow.")
    app_download_parser.add_argument("--app-config", default=None, help="Path to mac-app.json.")
    app_download_parser.add_argument("--force-redownload", action="store_true", help="Download again even if history or local files already exist.")

    app_parse_profile_parser = subparsers.add_parser("app-parse-profile", help="Parse a homepage URL for the macOS app.")
    app_parse_profile_parser.add_argument("--app-config", default=None, help="Path to mac-app.json.")
    app_parse_profile_parser.add_argument("--url", required=True, help="Homepage URL to parse.")

    app_publish_parser = subparsers.add_parser("app-publish", help="Run macOS app directory publish workflow.")
    app_publish_parser.add_argument("--app-config", default=None, help="Path to mac-app.json.")

    youtube_setup_parser = subparsers.add_parser("app-youtube-setup", help="Install/check YouTube PO Token helper for the macOS app.")
    youtube_setup_parser.add_argument("--json", action="store_true", help="Print result as JSON.")

    tencent_setup_parser = subparsers.add_parser("app-tencent-setup", help="Install/check Tencent channel skill for the macOS app.")
    tencent_setup_parser.add_argument("--check", action="store_true", help="Only check current Tencent channel status.")
    tencent_setup_parser.add_argument("--json", action="store_true", help="Print result as JSON.")

    return parser


def resolve_cli_path(value: str | None) -> Path | None:
    if not value:
        return None
    return Path(value).expanduser().resolve()


def apply_cli_overrides(config: AppConfig, args: argparse.Namespace) -> AppConfig:
    cli_profile_videos_count = getattr(args, "profile_videos_count", None)
    return AppConfig(
        output_dir=resolve_cli_path(getattr(args, "output_dir", None)) or config.output_dir,
        profile_dir=resolve_cli_path(getattr(args, "profile_dir", None)) or config.profile_dir,
        browser_path=(getattr(args, "browser_path", None) if getattr(args, "browser_path", None) is not None else config.browser_path),
        headless=(getattr(args, "headless", None) if getattr(args, "headless", None) is not None else config.headless),
        timeout_secs=(getattr(args, "timeout_secs", None) if getattr(args, "timeout_secs", None) is not None else config.timeout_secs),
        max_concurrent=config.max_concurrent,
        max_concurrent_per_site=config.max_concurrent_per_site,
        start_interval_secs=config.start_interval_secs,
        watermark=config.watermark,
        profile_videos_count=(cli_profile_videos_count if cli_profile_videos_count is not None else config.profile_videos_count),
        source_path=config.source_path,
    )


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = apply_cli_overrides(
            load_app_config(Path(args.config) if args.config else None, start_dir=Path.cwd()),
            args,
        )
        if args.command == "download":
            results = download_jobs(
                DownloadOptions(
                    raw_inputs=list(args.inputs),
                    input_file=resolve_cli_path(args.input_file),
                    output_dir=config.output_dir,
                    profile_dir=config.profile_dir,
                    browser_path=config.browser_path,
                    headless=config.headless,
                    timeout_secs=config.timeout_secs,
                    max_concurrent=config.max_concurrent,
                    max_concurrent_per_site=config.max_concurrent_per_site,
                    start_interval_secs=config.start_interval_secs,
                    watermark=config.watermark,
                    profile_videos_count=config.profile_videos_count,
                    profile_order=args.profile_order,
                    ytdlp_extractor_args=args.ytdlp_extractor_args,
                )
            )
            payload = [
                {
                    "ok": item.ok,
                    "raw_input": item.raw_input,
                    "output_path": str(item.artifact.output_path.resolve()) if item.artifact else "",
                    "sidecar_path": str(item.artifact.sidecar_path.resolve()) if item.artifact else "",
                    "chosen_candidate": item.artifact.chosen_candidate.to_dict() if item.artifact else None,
                    "site": item.extraction.metadata.site if item.extraction else (item.parsed_input.provider_key if item.parsed_input else ""),
                    "content_id": item.extraction.metadata.content_id if item.extraction else "",
                    "aweme_id": item.extraction.metadata.aweme_id if item.extraction else "",
                    "author": item.extraction.metadata.author if item.extraction else "",
                    "desc": item.extraction.metadata.desc if item.extraction else "",
                    "error": item.error,
                }
                for item in results
            ]
            if args.json:
                print(json.dumps(payload if len(payload) > 1 else payload[0], ensure_ascii=False, indent=2))
            else:
                for index, item in enumerate(payload):
                    if index:
                        print()
                    title_parts = [part for part in (item["site"], item["author"], item["content_id"]) if part]
                    if item["ok"]:
                        print("Downloaded " + " ".join(title_parts) if title_parts else "Downloaded video")
                        print(f"video: {item['output_path']}")
                        print(f"sidecar: {item['sidecar_path']}")
                    else:
                        print("Failed " + " ".join(title_parts) if title_parts else f"Failed {item['raw_input']}")
                        print(f"error: {item['error']}")
            return 0 if all(item["ok"] for item in payload) else 1

        if args.command == "prepare-list":
            output_file = resolve_cli_path(args.output_file)
            assert output_file is not None
            prepared = prepare_link_list(
                raw_inputs=list(args.inputs),
                input_file=resolve_cli_path(args.input_file),
                output_file=output_file,
                timeout_secs=config.timeout_secs,
            )
            unique_urls = list(dict.fromkeys(item.canonical_url for item in prepared))
            payload = {
                "output_file": str(output_file),
                "count": len(unique_urls),
                "items": unique_urls,
            }
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                print(f"Saved link list: {output_file}")
                print(f"count: {payload['count']}")
            return 0

        if args.command == "sync":
            from videocp.config import load_sync_config
            from videocp.sync import SyncOptions, run_sync

            sync_config = load_sync_config(
                tasks_path=Path(args.tasks_file) if args.tasks_file else None,
                start_dir=Path.cwd(),
            )
            results = run_sync(SyncOptions(
                app_config=config,
                sync_config=sync_config,
                dry_run=args.dry_run,
                task_name_filter=args.task_name,
                count_override=args.count,
            ))
            payload = [
                {
                    "task_name": r.task_name,
                    "ok": r.ok,
                    "action": r.action,
                    "content_id": r.content_id,
                    "feed_id": r.feed_id,
                    "share_url": r.share_url,
                    "output_path": r.output_path,
                    "error": r.error,
                }
                for r in results
            ]
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                for r in results:
                    status = r.action
                    if r.ok:
                        if r.action in ("synced", "synced_pinned"):
                            tag = "pinned" if r.action == "synced_pinned" else "synced"
                            print(f"[{tag}] {r.task_name}: {r.content_id}")
                            if r.share_url:
                                print(f"  share: {r.share_url}")
                            print(f"  video: {r.output_path}")
                        elif r.action == "skipped":
                            print(f"[skipped] {r.task_name}: {r.content_id} (already synced)")
                        elif r.action == "skipped_unavailable":
                            print(f"[skipped] {r.task_name}: {r.content_id} (unavailable source)")
                        elif r.action == "no_new_video":
                            print(f"[no_new] {r.task_name}: no new video found")
                        elif r.action == "skipped_random":
                            print(f"[skipped] {r.task_name}: {r.content_id} (randomly skipped)")
                        elif r.action == "dry_run":
                            print(f"[dry_run] {r.task_name}: would sync {r.content_id}")
                    else:
                        print(f"[failed] {r.task_name}: {r.error}")
            return 0 if all(r.ok for r in results) else 1

        if args.command == "mac-app":
            from videocp.mac_web_app import main as app_main

            app_args = []
            if args.app_config:
                # The GUI currently uses the default config path; keeping this
                # argument in the public CLI leaves room for alternate launchers.
                app_args.extend(["--app-config", args.app_config])
            return app_main(app_args)

        if args.command == "schedule":
            from videocp.mac_scheduler import main as scheduler_main

            scheduler_args = []
            if args.app_config:
                scheduler_args.extend(["--app-config", args.app_config])
            if args.once:
                scheduler_args.append("--once")
            if args.dry_run:
                scheduler_args.append("--dry-run")
            if args.task_name:
                scheduler_args.extend(["--task-name", args.task_name])
            return scheduler_main(scheduler_args)

        if args.command == "app-download":
            from videocp.mac_scheduler import default_app_config_path
            from videocp.mac_workflow import run_download_from_app_config

            path = Path(args.app_config).expanduser().resolve() if args.app_config else default_app_config_path(Path.cwd())
            results = run_download_from_app_config(path, force_redownload=args.force_redownload)
            print(json.dumps(results, ensure_ascii=False, indent=2))
            return 0 if all(item.get("ok") for item in results) else 1

        if args.command == "app-parse-profile":
            from videocp.mac_scheduler import default_app_config_path
            from videocp.mac_workflow import parse_profile_from_app_config

            path = Path(args.app_config).expanduser().resolve() if args.app_config else default_app_config_path(Path.cwd())
            result = parse_profile_from_app_config(path, args.url)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result.get("ok") else 1

        if args.command == "app-publish":
            from videocp.mac_scheduler import default_app_config_path
            from videocp.mac_workflow import run_publish_from_app_config

            path = Path(args.app_config).expanduser().resolve() if args.app_config else default_app_config_path(Path.cwd())
            results = run_publish_from_app_config(path)
            print(json.dumps(results, ensure_ascii=False, indent=2))
            return 0 if all(item.get("ok") for item in results) else 1

        if args.command == "app-youtube-setup":
            from videocp.youtube_po import ensure_provider_installed

            result = ensure_provider_installed(install=True)
            payload = result.to_dict()
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            elif result.ok:
                print(f"YouTube 下载组件已就绪: {result.package} {result.version}")
                print(f"yt-dlp 参数: {result.extractor_args}")
            else:
                print(f"YouTube 下载组件准备失败: {result.error}")
            return 0 if result.ok else 1

        if args.command == "app-tencent-setup":
            from videocp.tencent_skill import check_tencent_channel_skill, setup_tencent_channel_skill

            token = "" if args.check else (os.environ.get("QQ_AI_CONNECT_TOKEN_INPUT") or os.environ.get("QQ_AI_CONNECT_TOKEN") or "")
            result = check_tencent_channel_skill() if args.check else setup_tencent_channel_skill(token=token, install=True)
            payload = result.to_dict()
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            elif result.ok:
                print(f"腾讯频道已就绪，登录来源: {result.token_source or 'unknown'}")
            else:
                print(f"腾讯频道未就绪: {result.error}")
            return 0 if result.ok else 1

        checks = doctor(
            DoctorOptions(
                profile_dir=config.profile_dir,
                browser_path=config.browser_path,
                headless=config.headless,
                keep_open=args.keep_open,
                login_urls=list(args.login_urls),
            )
        )
        payload = [check.to_dict() for check in checks]
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            for check in checks:
                status = "ok" if check.ok else "fail"
                print(f"[{status}] {check.name}: {check.detail}")
        return 0 if all(check.ok for check in checks if check.name != "ffmpeg") else 1
    except (VideoCpError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
