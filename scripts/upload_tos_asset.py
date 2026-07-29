#!/usr/bin/env python3
"""
Upload local assets to Volcengine TOS and return URLs suitable for Yijia.

Default mode is private bucket + GET pre-signed URL. Secrets are read from
environment variables and are never printed.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import re
import sys
import urllib.parse


class TosConfigError(RuntimeError):
    pass


def load_local_env() -> None:
    script_dir = Path(__file__).resolve().parent
    candidates = [
        script_dir.parent / ".env.local",
        Path.home() / ".config" / "paper-collage-video.env",
    ]
    for env_path in candidates:
        if not env_path.is_file():
            continue
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export ") :].strip()
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
                continue
            if key in os.environ:
                continue
            value = value.strip()
            if (value.startswith('"') and value.endswith('"')) or (
                value.startswith("'") and value.endswith("'")
            ):
                value = value[1:-1]
            os.environ[key] = value


load_local_env()


def env_first(*names: str) -> str | None:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def normalize_endpoint(endpoint: str | None, region: str | None) -> tuple[str | None, str | None]:
    # Users often paste "cn-beijing" from the console "外网访问" field.
    if endpoint and "." not in endpoint and endpoint.startswith("cn-") and not region:
        region = endpoint
        endpoint = None
    if region and not endpoint:
        endpoint = f"tos-{region}.volces.com"
    if endpoint:
        endpoint = endpoint.removeprefix("https://").removeprefix("http://").strip("/")
    return endpoint, region


def load_config(args: argparse.Namespace | None = None) -> dict:
    args = args or argparse.Namespace()
    ak = getattr(args, "access_key", None) or env_first(
        "TOS_ACCESS_KEY_ID",
        "TOS_ACCESS_KEY",
        "VOLCENGINE_ACCESS_KEY_ID",
    )
    sk = getattr(args, "secret_key", None) or env_first(
        "TOS_SECRET_ACCESS_KEY",
        "TOS_SECRET_KEY",
        "VOLCENGINE_SECRET_ACCESS_KEY",
    )
    bucket = getattr(args, "bucket", None) or env_first("TOS_BUCKET")
    region = getattr(args, "region", None) or env_first("TOS_REGION")
    endpoint = getattr(args, "endpoint", None) or env_first("TOS_ENDPOINT")
    endpoint, region = normalize_endpoint(endpoint, region)

    missing = []
    if not ak:
        missing.append("TOS_ACCESS_KEY_ID")
    if not sk:
        missing.append("TOS_SECRET_ACCESS_KEY")
    if not bucket:
        missing.append("TOS_BUCKET")
    if not region:
        missing.append("TOS_REGION")
    if not endpoint:
        missing.append("TOS_ENDPOINT")
    if missing:
        raise TosConfigError("Missing TOS config: " + ", ".join(missing))

    return {
        "access_key": ak,
        "secret_key": sk,
        "bucket": bucket,
        "region": region,
        "endpoint": endpoint,
        "prefix": getattr(args, "prefix", None) or os.environ.get("TOS_PREFIX", "paper-collage-video/"),
        "url_mode": getattr(args, "url_mode", None) or os.environ.get("TOS_URL_MODE", "presign"),
        "presign_expires": int(
            getattr(args, "presign_expires", None) or os.environ.get("TOS_PRESIGN_EXPIRES", "86400")
        ),
        "public_base_url": getattr(args, "public_base_url", None) or os.environ.get("TOS_PUBLIC_BASE_URL"),
        "make_public_read": bool(
            getattr(args, "make_public_read", False)
            or os.environ.get("TOS_MAKE_PUBLIC_READ", "").lower() in {"1", "true", "yes"}
        ),
    }


def has_minimal_tos_env() -> bool:
    try:
        load_config(argparse.Namespace())
        return True
    except TosConfigError:
        return False


def safe_name(path: Path) -> str:
    stem = re.sub(r"[^a-zA-Z0-9._-]+", "-", path.stem).strip("-") or "asset"
    suffix = re.sub(r"[^a-zA-Z0-9.]+", "", path.suffix.lower())
    return stem[:80] + suffix


def file_hash(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()[:12]


def object_key_for(path: Path, prefix: str) -> str:
    today = dt.datetime.now().strftime("%Y/%m/%d")
    prefix = prefix.strip("/")
    parts = [part for part in (prefix, today, f"{file_hash(path)}-{safe_name(path)}") if part]
    return "/".join(parts)


def public_url(config: dict, key: str) -> str:
    quoted_key = urllib.parse.quote(key)
    if config.get("public_base_url"):
        return urllib.parse.urljoin(config["public_base_url"].rstrip("/") + "/", quoted_key)
    return f"https://{config['bucket']}.{config['endpoint']}/{quoted_key}"


def upload_asset_to_tos(path: str, *, config: dict | None = None) -> dict:
    local_path = Path(path).expanduser().resolve()
    if not local_path.is_file():
        raise TosConfigError(f"TOS upload source is not a file: {local_path}")

    config = config or load_config()
    try:
        import tos
    except ImportError as exc:
        raise TosConfigError("Python package 'tos' is not installed. Install with: python3 -m pip install --user tos") from exc

    key = object_key_for(local_path, config["prefix"])
    content_type = mimetypes.guess_type(str(local_path))[0] or "application/octet-stream"
    client = tos.TosClientV2(
        config["access_key"],
        config["secret_key"],
        config["endpoint"],
        config["region"],
    )
    acl = tos.ACLType.ACL_Public_Read if config["make_public_read"] else None
    result = client.put_object_from_file(
        config["bucket"],
        key,
        str(local_path),
        content_type=content_type,
        acl=acl,
    )
    status_code = getattr(result, "status_code", None)
    if status_code and int(status_code) >= 400:
        raise TosConfigError(f"TOS upload failed with status {status_code}")

    if config["url_mode"] == "public":
        url = public_url(config, key)
    elif config["url_mode"] == "presign":
        signed = client.pre_signed_url(
            tos.HttpMethodType.Http_Method_Get,
            config["bucket"],
            key,
            expires=config["presign_expires"],
        )
        url = signed.signed_url
    else:
        raise TosConfigError("TOS_URL_MODE must be 'presign' or 'public'")

    return {
        "path": str(local_path),
        "bucket": config["bucket"],
        "key": key,
        "content_type": content_type,
        "url": url,
        "url_mode": config["url_mode"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Upload local assets to Volcengine TOS.")
    parser.add_argument("paths", nargs="+", help="Local files to upload")
    parser.add_argument("--json", action="store_true", help="Print JSON output")
    parser.add_argument("--access-key")
    parser.add_argument("--secret-key")
    parser.add_argument("--bucket")
    parser.add_argument("--region")
    parser.add_argument("--endpoint")
    parser.add_argument("--prefix")
    parser.add_argument("--url-mode", choices=["presign", "public"])
    parser.add_argument("--presign-expires", type=int)
    parser.add_argument("--public-base-url")
    parser.add_argument("--make-public-read", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        config = load_config(args)
        results = [upload_asset_to_tos(path, config=config) for path in args.paths]
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for result in results:
            print(result["url"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
