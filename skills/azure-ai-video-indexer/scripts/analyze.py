#!/usr/bin/env python3
"""Analyze video with Azure Video Indexer.

Service: Azure Video Indexer
Task:    Upload, index, and extract insights from video
Env:     AZURE_VIDEO_INDEXER_ACCOUNT_ID  (required)
         AZURE_VIDEO_INDEXER_LOCATION    (required)
         AZURE_VIDEO_INDEXER_ACCESS_TOKEN (optional; auto-generated via az CLI)

Example:
    export AZURE_VIDEO_INDEXER_ACCOUNT_ID="<guid>"
    export AZURE_VIDEO_INDEXER_LOCATION="eastus2"
    export AZURE_VIDEO_INDEXER_ACCESS_TOKEN="<token>"
    python3 analyze.py --upload video.mp4 --name "My Video"

# Requires: Python >= 3.8, standard library only
"""

from __future__ import print_function

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request

# Ensure UTF-8 output on Windows (where stdout defaults to system code page)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_API_BASE = "https://api.videoindexer.ai"
_ARM_RESOURCE = "https://management.azure.com"
_ARM_API_VERSION = "2024-01-01"

_VIDEO_CONTENT_TYPES = {
    ".mp4": "video/mp4",
    ".avi": "video/x-msvideo",
    ".mov": "video/quicktime",
    ".wmv": "video/x-ms-wmv",
    ".mkv": "video/x-matroska",
    ".webm": "video/webm",
    ".flv": "video/x-flv",
    ".m4v": "video/x-m4v",
    ".3gp": "video/3gpp",
    ".ts": "video/mp2t",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _emit_error(what, hint):
    # type: (str, str) -> None
    """Print a structured JSON error to *stderr* for agent consumption."""
    msg = json.dumps({"error": str(what), "hint": hint})
    sys.stderr.write(msg + "\n")


def _guess_content_type(filepath):
    # type: (str) -> str
    """Guess video content type from file extension."""
    ext = os.path.splitext(filepath)[1].lower()
    return _VIDEO_CONTENT_TYPES.get(ext, "video/mp4")


# ---------------------------------------------------------------------------
# Token generation via az CLI + ARM
# ---------------------------------------------------------------------------


def _generate_token_via_az(account_id, location):
    # type: (str, str) -> str
    """Try to generate a Video Indexer access token using az CLI.

    Discovers the VI account via ``az resource list`` and generates a
    Contributor-scoped access token via the ARM API.  Returns the token
    string or raises RuntimeError.
    """
    # 1. Discover the VI account resource
    try:
        res = subprocess.run(
            ["az", "resource", "list",
             "--resource-type", "Microsoft.VideoIndexer/accounts",
             "--query",
             "[?properties.accountId=='{}'].{{name:name, rg:resourceGroup, "
             "id:id}}".format(account_id),
             "-o", "json"],
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise RuntimeError("az CLI not available or timed out")

    if res.returncode != 0:
        raise RuntimeError("az resource list failed: " + res.stderr.strip())
    accounts = json.loads(res.stdout)
    if not accounts:
        raise RuntimeError(
            "No Video Indexer account found with accountId=" + account_id
        )
    acct = accounts[0]
    resource_id = acct["id"]
    # Extract subscription ID from the resource ID
    # Format: /subscriptions/{subId}/resourceGroups/{rg}/providers/...
    parts = resource_id.split("/")
    sub_idx = parts.index("subscriptions") + 1
    sub_id = parts[sub_idx]

    # 2. Get ARM bearer token
    try:
        token_res = subprocess.run(
            ["az", "account", "get-access-token",
             "--resource", _ARM_RESOURCE,
             "--query", "accessToken", "-o", "tsv"],
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise RuntimeError("az account get-access-token failed")

    if token_res.returncode != 0:
        raise RuntimeError(
            "Cannot get ARM token: " + token_res.stderr.strip()
        )
    arm_token = token_res.stdout.strip()
    if not arm_token:
        raise RuntimeError("ARM token is empty")

    # 3. Call generateAccessToken via ARM API
    url = (
        "{}/subscriptions/{}/resourceGroups/{}"
        "/providers/Microsoft.VideoIndexer/accounts/{}"
        "/generateAccessToken?api-version={}"
    ).format(
        _ARM_RESOURCE, sub_id, acct["rg"],
        acct["name"], _ARM_API_VERSION,
    )
    body = json.dumps({
        "permissionType": "Contributor",
        "scope": "Account",
    }).encode("utf-8")
    headers = {
        "Authorization": "Bearer " + arm_token,
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(
        url, data=body, headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        raise RuntimeError(
            "ARM generateAccessToken returned HTTP {}: {}".format(
                exc.code, detail[:200]
            )
        )
    token = data.get("accessToken", "")
    if not token:
        raise RuntimeError("generateAccessToken returned no token")
    return token


def _resolve_token(account_id, location):
    # type: (str, str) -> str
    """Resolve access token from env var or auto-generate via az CLI."""
    token = os.environ.get("AZURE_VIDEO_INDEXER_ACCESS_TOKEN")
    if token:
        return token

    sys.stderr.write(
        "AZURE_VIDEO_INDEXER_ACCESS_TOKEN not set; "
        "trying auto-generation via az CLI...\n"
    )
    try:
        return _generate_token_via_az(account_id, location)
    except RuntimeError as exc:
        _emit_error(
            "Cannot resolve access token.",
            "Set AZURE_VIDEO_INDEXER_ACCESS_TOKEN or ensure 'az' CLI "
            "is logged in with access to the Video Indexer account. "
            "Detail: {}".format(exc),
        )
        raise


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _api_url(location, account_id, path, params=None):
    # type: (str, str, str, dict) -> str
    """Build a Video Indexer API URL."""
    base = "{}/{}/Accounts/{}{}".format(
        _API_BASE, location, account_id, path
    )
    if params:
        base += "?" + urllib.parse.urlencode(params)
    return base


def _api_get(url, token, timeout=60):
    # type: (str, str, int) -> dict
    """GET from the VI API with bearer auth."""
    headers = {"Authorization": "Bearer " + token}
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _api_post(url, token, data=None, content_type=None, timeout=120):
    # type: (str, str, bytes, str, int) -> dict
    """POST to the VI API with bearer auth."""
    headers = {"Authorization": "Bearer " + token}
    if content_type:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(
        url, data=data, headers=headers, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        if raw:
            return json.loads(raw)
        return {}


def _build_multipart(filepath):
    # type: (str) -> tuple
    """Build multipart/form-data body for video upload.

    Returns ``(body_bytes, content_type)``.
    """
    boundary = uuid.uuid4().hex
    ct = _guess_content_type(filepath)
    filename = os.path.basename(filepath)

    with open(filepath, "rb") as f:
        file_data = f.read()

    body = b""
    body += ("--{}\r\n".format(boundary)).encode()
    body += (
        'Content-Disposition: form-data; name="file"; '
        'filename="{}"\r\n'.format(filename)
    ).encode()
    body += ("Content-Type: {}\r\n\r\n".format(ct)).encode()
    body += file_data
    body += ("\r\n--{}--\r\n".format(boundary)).encode()

    content_type = "multipart/form-data; boundary={}".format(boundary)
    return body, content_type


# ---------------------------------------------------------------------------
# Error hints
# ---------------------------------------------------------------------------


def _hint_for_http_error(code, detail):
    # type: (int, str) -> str
    """Return an actionable hint for the HTTP status code."""
    if code == 401:
        return (
            "Access token expired or invalid. Generate a new one: "
            "az CLI + ARM API or set AZURE_VIDEO_INDEXER_ACCESS_TOKEN."
        )
    if code == 403:
        return (
            "Forbidden. Check that your token has Contributor permission "
            "and the account ID is correct."
        )
    if code == 404:
        return (
            "Not found. Verify AZURE_VIDEO_INDEXER_ACCOUNT_ID, "
            "AZURE_VIDEO_INDEXER_LOCATION, and the video ID."
        )
    if code == 409:
        return "Conflict. A video with the same name may already exist."
    if code == 429:
        return "Rate limited. Wait and retry."
    if code >= 500:
        return "Server error ({}). Retry later.".format(code)
    return "HTTP {}: {}".format(code, detail[:200] if detail else "unknown")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv=None):
    # type: (list) -> argparse.Namespace
    """Parse command-line arguments."""
    p = argparse.ArgumentParser(
        description=(
            "Analyze video with Azure Video Indexer. "
            "Upload videos, get insights, or list indexed videos."
        ),
    )
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--upload", dest="upload_path",
        help="Video file to upload and index.",
    )
    mode.add_argument(
        "--video-url",
        help="Publicly accessible video URL to index.",
    )
    mode.add_argument(
        "--video-id",
        help="Get insights for an already-indexed video.",
    )
    mode.add_argument(
        "--list", action="store_true", dest="list_videos",
        help="List indexed videos.",
    )
    p.add_argument(
        "--name",
        help="Video name (for upload/URL indexing; default: filename).",
    )
    p.add_argument(
        "--language", default="auto",
        help="Video language or 'auto' (default: %(default)s).",
    )
    p.add_argument(
        "--privacy", default="Private",
        choices=["Private", "Public"],
        help="Video privacy (default: %(default)s).",
    )
    p.add_argument(
        "--wait", action="store_true", default=True,
        help="Wait for indexing to complete (default: true).",
    )
    p.add_argument(
        "--no-wait", action="store_false", dest="wait",
        help="Return immediately after upload (don't wait).",
    )
    p.add_argument(
        "--poll-interval", type=int, default=30,
        help="Seconds between status polls (default: %(default)s).",
    )
    p.add_argument(
        "--max-wait", type=int, default=3600,
        help="Max seconds to wait for indexing (default: %(default)s).",
    )
    p.add_argument(
        "--account-id", default=None,
        help="Video Indexer account ID (GUID).",
    )
    p.add_argument(
        "--location", default=None,
        help="Video Indexer location (e.g. 'eastus2', 'trial').",
    )
    p.add_argument(
        "--timeout", type=int, default=120,
        help="HTTP timeout per request in seconds (default: %(default)s).",
    )
    p.add_argument(
        "--raw", action="store_true",
        help="Print the full API JSON response.",
    )
    return p.parse_args(argv)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv=None):
    # type: (list) -> int
    """Entry point. Returns 0 on success, 1 on failure."""
    args = parse_args(argv)

    # ---- Resolve account ----
    account_id = (
        args.account_id
        or os.environ.get("AZURE_VIDEO_INDEXER_ACCOUNT_ID")
    )
    if not account_id:
        _emit_error(
            "No account ID specified.",
            "Set AZURE_VIDEO_INDEXER_ACCOUNT_ID or pass --account-id. "
            "Find it in the Azure portal > Video Indexer > Overview.",
        )
        return 1

    location = (
        args.location
        or os.environ.get("AZURE_VIDEO_INDEXER_LOCATION")
    )
    if not location:
        _emit_error(
            "No location specified.",
            "Set AZURE_VIDEO_INDEXER_LOCATION or pass --location "
            "(e.g. 'eastus2', 'trial').",
        )
        return 1

    # ---- Resolve token ----
    try:
        token = _resolve_token(account_id, location)
    except RuntimeError:
        return 1

    # ---- List videos ----
    if args.list_videos:
        return _cmd_list(account_id, location, token, args)

    # ---- Get insights for existing video ----
    if args.video_id:
        return _cmd_insights(account_id, location, token, args)

    # ---- Upload video file ----
    if args.upload_path:
        return _cmd_upload_file(account_id, location, token, args)

    # ---- Index video from URL ----
    if args.video_url:
        return _cmd_upload_url(account_id, location, token, args)

    _emit_error("No action specified.", "Use --upload, --video-url, --video-id, or --list.")
    return 1


def _cmd_list(account_id, location, token, args):
    # type: (str, str, str, argparse.Namespace) -> int
    """List indexed videos."""
    url = _api_url(location, account_id, "/Videos")
    try:
        result = _api_get(url, token, timeout=args.timeout)
    except urllib.error.HTTPError as exc:
        return _handle_http_error(exc)
    except urllib.error.URLError as exc:
        _emit_error("Connection failed: {}".format(exc.reason), "Check network.")
        return 1

    if args.raw:
        json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    videos = result.get("results", [])
    output = []
    for v in videos:
        output.append({
            "id": v.get("id", ""),
            "name": v.get("name", ""),
            "state": v.get("state", ""),
            "duration": v.get("durationInSeconds", 0),
            "created": v.get("created", ""),
        })
    json.dump({"count": len(output), "videos": output}, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def _cmd_insights(account_id, location, token, args):
    # type: (str, str, str, argparse.Namespace) -> int
    """Get insights for an existing video."""
    url = _api_url(location, account_id, "/Videos/{}/Index".format(args.video_id))
    try:
        result = _api_get(url, token, timeout=args.timeout)
    except urllib.error.HTTPError as exc:
        return _handle_http_error(exc)
    except urllib.error.URLError as exc:
        _emit_error("Connection failed: {}".format(exc.reason), "Check network.")
        return 1

    return _print_insights(result, args.raw)


def _cmd_upload_file(account_id, location, token, args):
    # type: (str, str, str, argparse.Namespace) -> int
    """Upload a video file and optionally wait for indexing."""
    if not os.path.isfile(args.upload_path):
        _emit_error(
            "File not found: '{}'.".format(args.upload_path),
            "Check the path and ensure the file exists.",
        )
        return 1

    name = args.name or os.path.splitext(os.path.basename(args.upload_path))[0]
    params = {
        "name": name,
        "privacy": args.privacy,
        "language": args.language,
    }
    url = _api_url(location, account_id, "/Videos", params)

    body, content_type = _build_multipart(args.upload_path)
    sys.stderr.write("Uploading '{}'...\n".format(args.upload_path))

    try:
        result = _api_post(url, token, data=body,
                           content_type=content_type, timeout=args.timeout)
    except urllib.error.HTTPError as exc:
        return _handle_http_error(exc)
    except urllib.error.URLError as exc:
        _emit_error("Connection failed: {}".format(exc.reason), "Check network.")
        return 1

    video_id = result.get("id", "")
    sys.stderr.write("Video uploaded. ID: {}\n".format(video_id))

    if args.wait and video_id:
        return _poll_until_done(account_id, location, token, video_id, args)

    json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


def _cmd_upload_url(account_id, location, token, args):
    # type: (str, str, str, argparse.Namespace) -> int
    """Index a video from a public URL."""
    name = args.name or "video"
    params = {
        "name": name,
        "videoUrl": args.video_url,
        "privacy": args.privacy,
        "language": args.language,
    }
    url = _api_url(location, account_id, "/Videos", params)

    sys.stderr.write("Submitting URL for indexing...\n")

    try:
        result = _api_post(url, token, timeout=args.timeout)
    except urllib.error.HTTPError as exc:
        return _handle_http_error(exc)
    except urllib.error.URLError as exc:
        _emit_error("Connection failed: {}".format(exc.reason), "Check network.")
        return 1

    video_id = result.get("id", "")
    sys.stderr.write("Video submitted. ID: {}\n".format(video_id))

    if args.wait and video_id:
        return _poll_until_done(account_id, location, token, video_id, args)

    json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


def _poll_until_done(account_id, location, token, video_id, args):
    # type: (str, str, str, str, argparse.Namespace) -> int
    """Poll video index until processing completes."""
    url = _api_url(location, account_id, "/Videos/{}/Index".format(video_id))
    elapsed = 0

    while elapsed < args.max_wait:
        time.sleep(args.poll_interval)
        elapsed += args.poll_interval
        sys.stderr.write(
            "Polling status ({}s elapsed)...\n".format(elapsed)
        )
        try:
            result = _api_get(url, token, timeout=args.timeout)
        except urllib.error.HTTPError as exc:
            return _handle_http_error(exc)
        except urllib.error.URLError as exc:
            sys.stderr.write(
                "Connection error during poll: {}\n".format(exc.reason)
            )
            continue

        state = result.get("state", "")
        if state == "Processed":
            sys.stderr.write("Indexing complete.\n")
            return _print_insights(result, args.raw)
        if state == "Failed":
            _emit_error(
                "Video indexing failed.",
                "Check the video format and try again. "
                "Video ID: {}".format(video_id),
            )
            return 1

    _emit_error(
        "Timed out after {}s waiting for indexing.".format(args.max_wait),
        "Video ID: {}. Check status later with "
        "--video-id {}.".format(video_id, video_id),
    )
    return 1


def _print_insights(result, raw):
    # type: (dict, bool) -> int
    """Print video insights."""
    if raw:
        json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    videos = result.get("videos", [])
    if not videos:
        json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    insights = videos[0].get("insights", {})

    output = {
        "name": result.get("name", ""),
        "state": result.get("state", ""),
        "duration": result.get("durationInSeconds", 0),
    }

    # Extract key insights
    if insights.get("transcript"):
        output["transcript"] = [
            {
                "text": t.get("text", ""),
                "start": t.get("adjustedTimeOffset", t.get("timeOffset", "")),
                "end": t.get("adjustedEndTimeOffset",
                             t.get("endTimeOffset", "")),
            }
            for t in insights["transcript"]
        ]

    if insights.get("topics"):
        output["topics"] = [
            {"name": t.get("name", ""), "confidence": t.get("confidence", 0)}
            for t in insights["topics"]
        ]

    if insights.get("keywords"):
        output["keywords"] = [
            {"text": k.get("text", ""), "confidence": k.get("confidence", 0)}
            for k in insights["keywords"]
        ]

    if insights.get("labels"):
        output["labels"] = [
            {"name": lb.get("name", ""), "confidence": lb.get("confidence", 0)}
            for lb in insights["labels"]
        ]

    if insights.get("sentiments"):
        output["sentiments"] = [
            {
                "sentimentType": s.get("sentimentType", ""),
                "averageScore": s.get("averageScore", 0),
            }
            for s in insights["sentiments"]
        ]

    if insights.get("faces"):
        output["faces"] = [
            {
                "id": fc.get("id", ""),
                "name": fc.get("name", ""),
                "confidence": fc.get("confidence", 0),
            }
            for fc in insights["faces"]
        ]

    json.dump(output, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


def _handle_http_error(exc):
    # type: (urllib.error.HTTPError) -> int
    """Handle an HTTPError and return exit code 1."""
    detail = ""
    try:
        detail = exc.read().decode("utf-8", errors="replace")
    except Exception:
        pass
    _emit_error(
        "HTTP {} from Video Indexer API.".format(exc.code),
        _hint_for_http_error(exc.code, detail),
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
