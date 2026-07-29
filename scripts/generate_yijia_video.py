#!/usr/bin/env python3
"""
Submit image-to-video jobs to the Yijia /v1/videos API, poll completion, and
download the no-watermark video URL when available.

Secrets are read from YIJIA_API_KEY by default and are never printed.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from upload_tos_asset import TosConfigError, has_minimal_tos_env, upload_asset_to_tos


DEFAULT_BASE_URL = "https://api.yijiarj.cn"
URL_RE = re.compile(r"https?://[^\s\"'<>()]+", re.IGNORECASE)
VIDEO_EXT_RE = re.compile(r"\.(mp4|mov|webm|m3u8)(?:[?#].*)?$", re.IGNORECASE)
PERMISSION_ERROR_RE = re.compile(
    r"permission|unauthorized|forbidden|invalid api key|insufficient|quota|billing",
    re.IGNORECASE,
)
MODEL_CONFIG_ERROR_RE = re.compile(
    r"model_not_found|no available channel for model|model .* not found",
    re.IGNORECASE,
)


class ApiError(RuntimeError):
    pass


def redact_url(url: str) -> str:
    try:
        parsed = urllib.parse.urlsplit(url)
    except ValueError:
        return url
    if not parsed.query:
        return url
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, "[REDACTED_QUERY]", parsed.fragment)
    )


def redact(text: str, api_key: str | None) -> str:
    if api_key:
        text = text.replace(api_key, "[REDACTED]")
        if not api_key.startswith("Bearer "):
            text = text.replace(f"Bearer {api_key}", "Bearer [REDACTED]")
    return URL_RE.sub(lambda match: redact_url(match.group(0)), text)


def classify_error(message: str) -> str:
    if MODEL_CONFIG_ERROR_RE.search(message):
        return "PROVIDER_MODEL_CONFIG_ERROR"
    if PERMISSION_ERROR_RE.search(message):
        return "PROVIDER_PERMISSION_ERROR"
    return "ERROR"


def get_api_key(args: argparse.Namespace) -> str | None:
    return args.api_key or os.environ.get("YIJIA_API_KEY")


def bearer_value(api_key: str) -> str:
    return api_key if api_key.startswith("Bearer ") else f"Bearer {api_key}"


def normalize_base_url(value: str) -> str:
    return value.rstrip("/")


def endpoint_url(base_url: str, path: str) -> str:
    return normalize_base_url(base_url) + "/" + path.lstrip("/")


def request_json(
    method: str,
    url: str,
    api_key: str,
    *,
    payload: dict | None = None,
    timeout: int = 60,
) -> dict:
    body = None
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method=method.upper(),
        headers={
            "Authorization": bearer_value(api_key),
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        raise ApiError(f"HTTP {exc.code}: {redact(raw[:1000], api_key)}") from exc
    except urllib.error.URLError as exc:
        raise ApiError(f"Network error: {exc}") from exc

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ApiError(f"Non-JSON response: {redact(raw[:1000], api_key)}") from exc
    if not isinstance(parsed, dict):
        raise ApiError(f"Unexpected JSON response: {parsed!r}")
    return parsed


def as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        items = value
    else:
        items = re.split(r"[|,]", str(value))
    return [str(item).strip() for item in items if str(item).strip()]


def is_http_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()
    return slug[:50] or "video"


def public_url_for_local_path(path: str, args: argparse.Namespace, job: dict | None = None) -> str:
    root = (
        (job or {}).get("public_asset_root")
        or args.public_asset_root
        or os.environ.get("YIJIA_PUBLIC_ASSET_ROOT")
    )
    base_url = (
        (job or {}).get("public_asset_base_url")
        or args.public_asset_base_url
        or os.environ.get("YIJIA_PUBLIC_ASSET_BASE_URL")
    )
    if not root or not base_url:
        raise ApiError(
            "Yijia input_reference requires public image/video URLs. "
            f"Local file cannot be sent directly: {path}. Configure TOS_* variables, "
            "YIJIA_PUBLIC_ASSET_ROOT/YIJIA_PUBLIC_ASSET_BASE_URL, or use public URLs."
        )

    local = Path(path).expanduser().resolve()
    public_root = Path(root).expanduser().resolve()
    try:
        relative = local.relative_to(public_root)
    except ValueError as exc:
        raise ApiError(f"Local file is outside YIJIA_PUBLIC_ASSET_ROOT: {local}") from exc

    base = base_url.rstrip("/") + "/"
    return urllib.parse.urljoin(base, urllib.parse.quote(str(relative).replace(os.sep, "/")))


def tos_url_for_local_path(path: str) -> str:
    try:
        result = upload_asset_to_tos(path)
    except TosConfigError:
        raise
    except Exception as exc:
        raise ApiError(f"TOS upload failed for {path}: {exc}") from exc
    print(f"Uploaded local asset to TOS: {result['key']}")
    return result["url"]


def local_media_url(path: str, args: argparse.Namespace, job: dict | None = None) -> str:
    mode = (job or {}).get("local_media_mode") or args.local_media_mode
    if mode == "tos":
        return tos_url_for_local_path(path)
    if mode == "public-map":
        return public_url_for_local_path(path, args, job)
    if mode != "auto":
        raise ApiError(f"Unsupported local media mode: {mode}")

    if has_minimal_tos_env():
        return tos_url_for_local_path(path)
    root = (
        (job or {}).get("public_asset_root")
        or args.public_asset_root
        or os.environ.get("YIJIA_PUBLIC_ASSET_ROOT")
    )
    base_url = (
        (job or {}).get("public_asset_base_url")
        or args.public_asset_base_url
        or os.environ.get("YIJIA_PUBLIC_ASSET_BASE_URL")
    )
    if root and base_url:
        return public_url_for_local_path(path, args, job)
    raise ApiError(
        "Local media needs a public URL for Yijia. Configure TOS_* variables, "
        "configure YIJIA_PUBLIC_ASSET_ROOT/YIJIA_PUBLIC_ASSET_BASE_URL, or use public URLs."
    )


def resolve_media_urls(value, args: argparse.Namespace, job: dict | None = None) -> list[str]:
    urls = []
    for item in as_list(value):
        if is_http_url(item):
            urls.append(item)
        elif os.path.exists(os.path.expanduser(item)):
            urls.append(local_media_url(item, args, job))
        else:
            raise ApiError(f"Media reference is neither a URL nor an existing local file: {item}")
    return urls


def parse_duration_seconds(value) -> int:
    if value is None or str(value).strip() == "":
        return 6
    clean = str(value).strip().lower()
    if clean.endswith("s"):
        clean = clean[:-1]
    try:
        number = float(clean)
    except ValueError as exc:
        raise ApiError(f"Invalid duration: {value}") from exc
    if not number.is_integer():
        raise ApiError(f"Duration must be whole seconds, got: {value}")
    seconds = int(number)
    if seconds not in {4, 6, 8, 10}:
        raise ApiError(f"Yijia omni duration must be one of 4, 6, 8, 10 seconds, got: {seconds}")
    return seconds


def aspect_ratio_from_size(size: str) -> str | None:
    match = re.match(r"^\s*(\d+)\s*x\s*(\d+)\s*$", str(size or ""))
    if not match:
        return None
    width = int(match.group(1))
    height = int(match.group(2))
    if height > width:
        return "9:16"
    if width > height:
        return "16:9"
    return None


def set_nested_field(payload: dict, field_path: str, value) -> None:
    parts = [part for part in field_path.split(".") if part]
    if not parts:
        return
    target = payload
    for part in parts[:-1]:
        child = target.get(part)
        if not isinstance(child, dict):
            child = {}
            target[part] = child
        target = child
    target[parts[-1]] = value


def extract_task_id(response: dict) -> str:
    candidates = []
    data = response.get("data")
    if isinstance(data, dict):
        candidates.extend(data.get(key) for key in ("id", "task_id", "taskId", "job_id"))
    candidates.extend(response.get(key) for key in ("id", "task_id", "taskId", "job_id"))
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    raise ApiError(f"Submit response did not include a task id: {response}")


def extract_status(detail: dict) -> str | None:
    data = detail.get("data")
    if isinstance(data, dict) and data.get("status") is not None:
        return str(data.get("status"))
    if detail.get("status") is not None:
        return str(detail.get("status"))
    return None


def detail_value(detail: dict, key: str):
    data = detail.get("data")
    if isinstance(data, dict) and key in data:
        return data.get(key)
    return detail.get(key)


def extract_error_message(detail: dict) -> str:
    for key in ("message", "msg", "error", "quality"):
        value = detail_value(detail, key)
        if value:
            return str(value)
    return json.dumps(detail, ensure_ascii=False)[:1000]


def is_success_status(status: str | None) -> bool:
    return (status or "").lower() in {"completed", "success", "succeeded", "done"}


def is_failed_status(status: str | None) -> bool:
    return (status or "").lower() in {"error", "failed", "cancelled", "canceled"}


def extract_download_url(detail: dict) -> str | None:
    value = detail_value(detail, "url")
    if isinstance(value, str) and value.startswith(("http://", "https://")):
        return value
    return None


def download_file(url: str, output_path: str, api_key: str | None = None) -> None:
    parent = os.path.dirname(output_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    print(f"Downloading generated video to: {output_path}")
    req = urllib.request.Request(url, headers={"Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=480) as resp, open(output_path, "wb") as out:
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        raise ApiError(f"Download failed HTTP {exc.code}: {redact(raw[:1000], api_key)}") from exc


def write_run_result(result: dict, api_key: str | None = None) -> None:
    output_path = result.get("output_path")
    if not output_path:
        return
    run_dir = Path(output_path).expanduser().resolve().parent
    run_dir.mkdir(parents=True, exist_ok=True)
    safe = json.loads(redact(json.dumps(result, ensure_ascii=False), api_key))
    with (run_dir / "run-result.json").open("w", encoding="utf-8") as handle:
        json.dump(safe, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def submit_job(job: dict, args: argparse.Namespace, api_key: str) -> str:
    prompt = job.get("prompt")
    if not prompt:
        raise ApiError("Job is missing required field: prompt")

    model = job.get("model") or args.model
    size = job.get("size") or args.size
    duration = parse_duration_seconds(job.get("duration", args.duration))
    references = job.get("input_reference", job.get("images", job.get("image")))
    reference_urls = resolve_media_urls(references, args, job)

    payload = {
        "prompt": prompt,
        "model": model,
        "size": size,
    }
    if args.duration_field:
        if args.duration_field.startswith("response_format."):
            payload.setdefault("response_format", {})
            payload["response_format"].setdefault("type", "video")
            aspect_ratio = aspect_ratio_from_size(size)
            if aspect_ratio:
                payload["response_format"].setdefault("aspect_ratio", aspect_ratio)
            set_nested_field(payload, args.duration_field, str(duration))
        else:
            set_nested_field(payload, args.duration_field, duration)
    if reference_urls:
        payload["input_reference"] = "|".join(reference_urls)
    remix_id = job.get("remix_id") or args.remix_id
    if remix_id:
        payload["remix_id"] = remix_id

    extra = job.get("extra")
    if isinstance(extra, dict):
        payload.update(extra)

    print(
        f"Submitting Yijia video job: model={model}, size={size}, "
        f"duration={duration}s, references={len(reference_urls)}"
    )
    response = request_json(
        "POST",
        endpoint_url(args.base_url, "/v1/videos"),
        api_key,
        payload=payload,
        timeout=args.request_timeout,
    )
    task_id = extract_task_id(response)
    print(f"Submitted task id: {task_id}")
    return task_id


def poll_job(task_id: str, args: argparse.Namespace, api_key: str) -> dict:
    deadline = time.time() + args.timeout
    last_printed = None
    detail_url = endpoint_url(args.base_url, "/v1/videos/" + urllib.parse.quote(task_id, safe=""))
    while time.time() < deadline:
        detail = request_json("GET", detail_url, api_key, timeout=args.request_timeout)
        status = extract_status(detail)
        progress = detail_value(detail, "progress")
        printable = (status, progress)
        if printable != last_printed:
            if progress is None:
                print(f"Task {task_id} status: {status}")
            else:
                print(f"Task {task_id} status: {status}, progress: {progress}")
            last_printed = printable

        if is_success_status(status):
            quality = detail_value(detail, "quality")
            if quality and str(quality).lower() != "standard":
                raise ApiError(f"Task {task_id} completed but quality check failed: {quality}")
            if not extract_download_url(detail):
                raise ApiError(f"Task {task_id} completed but no no-watermark url was returned")
            return detail
        if is_failed_status(status):
            raise ApiError(f"Task {task_id} failed: {extract_error_message(detail)}")
        time.sleep(args.poll_interval)
    raise ApiError(f"Task {task_id} timed out after {args.timeout} seconds")


def run_job(job: dict, args: argparse.Namespace, api_key: str) -> dict:
    output_path = job.get("output") or args.output
    if not output_path:
        output_path = f"media/output_{slugify(str(job.get('prompt', 'video')))}.mp4"

    task_id = None
    detail = None
    download_url = None
    try:
        task_id = submit_job(job, args, api_key)
        detail = poll_job(task_id, args, api_key)
        download_url = extract_download_url(detail)
        if not download_url:
            raise ApiError("Task succeeded but no downloadable URL was found")
        download_file(download_url, output_path, api_key)
        result = {
            "job": job,
            "status": "SUCCESS",
            "task_id": task_id,
            "output_path": output_path,
            "download_url": download_url,
            "detail_response": detail,
        }
    except Exception as exc:
        message = str(exc)
        result = {
            "job": job,
            "status": "FAILED",
            "error_type": classify_error(message),
            "error": message,
            "task_id": task_id,
            "output_path": output_path,
            "download_url": download_url,
            "detail_response": detail,
        }
    write_run_result(result, api_key)
    return result


def load_jobs(args: argparse.Namespace) -> list[dict]:
    if args.batch:
        with open(args.batch, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
        if isinstance(raw, dict):
            raw = raw.get("jobs")
        if not isinstance(raw, list):
            raise ApiError("Batch JSON must contain a list of job objects or a {'jobs': [...]} object")
        return raw
    if not args.prompt:
        raise ApiError("Provide a prompt or --batch")
    return [
        {
            "prompt": args.prompt,
            "model": args.model,
            "input_reference": args.input_reference or args.image,
            "size": args.size,
            "duration": args.duration,
            "remix_id": args.remix_id,
            "output": args.output or "media/output.mp4",
        }
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate videos with the Yijia /v1/videos API.")
    parser.add_argument("prompt", nargs="?", help="Prompt for a single generation")
    parser.add_argument("--batch", help="JSON file containing a list of jobs")
    parser.add_argument("--image", action="append", help="Public image URL, or local path with public asset mapping")
    parser.add_argument("--input-reference", action="append", help="Public reference URL(s), local path(s), or pipe-separated references")
    parser.add_argument("--model", default=os.environ.get("YIJIA_VIDEO_MODEL", "omni_flash_nowater"))
    parser.add_argument("--size", default=os.environ.get("YIJIA_VIDEO_SIZE", "720x1280"))
    parser.add_argument("--duration", default=os.environ.get("YIJIA_VIDEO_DURATION", "6"), help="Duration in seconds; allowed: 4, 6, 8, 10")
    parser.add_argument("--duration-field", default=os.environ.get("YIJIA_DURATION_FIELD", "response_format.duration"), help="Request field path for duration; default follows Gemini Interactions API response_format.duration")
    parser.add_argument("--remix-id")
    parser.add_argument("--output", help="Output mp4 path for single generation")
    parser.add_argument("--concurrency", type=int, default=1, help="Parallel jobs for --batch")
    parser.add_argument("--api-key", help="Yijia API key; defaults to YIJIA_API_KEY")
    parser.add_argument("--base-url", default=os.environ.get("YIJIA_API_BASE", DEFAULT_BASE_URL))
    parser.add_argument("--poll-interval", type=int, default=int(os.environ.get("YIJIA_POLL_INTERVAL", "5")))
    parser.add_argument("--timeout", type=int, default=int(os.environ.get("YIJIA_TIMEOUT", "900")))
    parser.add_argument("--request-timeout", type=int, default=60)
    parser.add_argument("--continue-on-error", action="store_true", help="Keep submitting remaining batch jobs after a failure")
    parser.add_argument("--public-asset-root", help="Local root that maps to a public URL base")
    parser.add_argument("--public-asset-base-url", help="Public URL base for --public-asset-root")
    parser.add_argument(
        "--local-media-mode",
        choices=["auto", "tos", "public-map"],
        default=os.environ.get("YIJIA_LOCAL_MEDIA_MODE", "auto"),
        help="How to turn local media paths into URLs (default: auto, prefer TOS when configured)",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args.base_url = normalize_base_url(args.base_url)
    api_key = get_api_key(args)
    if not api_key:
        print("Error: YIJIA_API_KEY is not set.", file=sys.stderr)
        return 1

    try:
        jobs = load_jobs(args)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Loaded {len(jobs)} Yijia video job(s).")
    max_workers = max(1, args.concurrency)
    results = []
    stopped_early = False
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        job_iter = iter(jobs)
        futures = {}

        def submit_next() -> None:
            try:
                job = next(job_iter)
            except StopIteration:
                return
            futures[executor.submit(run_job, job, args, api_key)] = job

        for _ in range(max_workers):
            submit_next()

        while futures:
            for future in as_completed(list(futures)):
                futures.pop(future, None)
                result = future.result()
                results.append(result)
                if result["status"] == "FAILED":
                    print(f"[FAILED] {result.get('error')}", file=sys.stderr)
                    if args.batch and not args.continue_on_error:
                        print("Stopping this batch before submitting more jobs.", file=sys.stderr)
                        stopped_early = True
                        break
                else:
                    print(f"[SUCCESS] {result['output_path']}")
                submit_next()
                break
            if stopped_early:
                for pending in futures:
                    pending.cancel()
                break

    success_count = sum(1 for item in results if item["status"] == "SUCCESS")
    failed_count = len(results) - success_count
    if stopped_early:
        print(f"Summary: submitted={len(results)} success={success_count} failed={failed_count} stopped_early=true")
    else:
        print(f"Summary: total={len(results)} success={success_count} failed={failed_count}")
    return 1 if failed_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
