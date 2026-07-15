#!/usr/bin/env python3
import argparse
import csv
import getpass
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

DEFAULT_BASE_URL = "https://api.anewknot.com"
DEFAULT_GRAPH_VERSION = "v25.0"


class ScriptError(Exception):
    def __init__(self, message, exit_code=5):
        super().__init__(message)
        self.exit_code = exit_code


class HostedClient:
    def __init__(self, base_url):
        parsed = urlparse(base_url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ScriptError("Base URL must be HTTPS", 3)
        self.base_url = base_url.rstrip("/")
        self.hostname = parsed.hostname
        self.session = requests.Session()
        self.jwt = ""

    def request(self, method, path, **kwargs):
        headers = dict(kwargs.pop("headers", {}))
        if self.jwt:
            headers["Authorization"] = f"Bearer {self.jwt}"
        try:
            response = self.session.request(
                method,
                urljoin(f"{self.base_url}/", path.lstrip("/")),
                headers=headers,
                timeout=(5, 60),
                allow_redirects=False,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise ScriptError(f"Hosted API request failed: {exc}", 3) from exc
        if 300 <= response.status_code < 400:
            raise ScriptError("Hosted API returned an unexpected redirect", 3)
        try:
            payload = response.json()
        except ValueError as exc:
            raise ScriptError(f"Hosted API returned non-JSON HTTP {response.status_code}", 3) from exc
        if not response.ok:
            raise ScriptError(payload.get("detail") or payload.get("error") or f"Hosted API HTTP {response.status_code}", 3)
        return payload

    def login(self, email, password):
        payload = self.request("POST", "/api/auth/login/", json={"email": email, "password": password})
        user = payload.get("user") or {}
        if user.get("role") not in {"admin", "super_admin"}:
            raise ScriptError("The account is not an admin or super admin", 3)
        self.jwt = (payload.get("tokens") or {}).get("access") or ""
        if not self.jwt:
            raise ScriptError("Login succeeded without an access token", 3)
        return user

    def preview(self, graph_token, waba_ids):
        return self.request(
            "POST",
            "/api/whatsapp/reconciliation/preview/",
            json={"graph_api_version": DEFAULT_GRAPH_VERSION, "access_token": graph_token, "waba_ids": waba_ids},
        )


class GraphClient:
    def __init__(self, token, version):
        self.token = token
        self.base = f"https://graph.facebook.com/{version}"
        self.session = requests.Session()

    def request(self, method, path, **kwargs):
        headers = dict(kwargs.pop("headers", {}))
        headers["Authorization"] = f"Bearer {self.token}"
        url = path if str(path).startswith("https://") else f"{self.base}/{str(path).lstrip('/')}"
        try:
            response = self.session.request(method, url, headers=headers, timeout=(5, 30), **kwargs)
        except requests.RequestException as exc:
            return None, {"message": str(exc), "transport_error": True}, 0
        try:
            payload = response.json() if response.content else {}
        except ValueError:
            payload = {"raw": response.text[:500]}
        if response.ok and "error" not in payload:
            return payload, None, response.status_code
        return None, payload.get("error") or payload, response.status_code

    def get_all(self, path, params=None):
        rows = []
        url = path
        next_params = params
        while url:
            payload, error, status_code = self.request("GET", url, params=next_params)
            if error:
                return rows, error, status_code
            rows.extend(payload.get("data") or [])
            url = (payload.get("paging") or {}).get("next")
            next_params = None
        return rows, None, 200

    def templates(self, waba_id):
        return self.get_all(
            f"{waba_id}/message_templates",
            {"fields": "name,status,language,category,components", "limit": 100},
        )

    def send(self, phone_number_id, payload):
        return self.request("POST", f"{phone_number_id}/messages", json=payload)


def norm_digits(value):
    return "".join(char for char in str(value or "") if char.isdigit())


def template_is_sendable_without_components(template):
    for component in template.get("components") or []:
        component_type = str(component.get("type") or "").upper()
        component_format = str(component.get("format") or "").upper()
        text = str(component.get("text") or "")
        if "{{" in text and "}}" in text:
            return False
        if component_type == "HEADER" and component_format in {"IMAGE", "VIDEO", "DOCUMENT", "LOCATION"}:
            return False
        if component_type == "BUTTONS":
            for button in component.get("buttons") or []:
                if "{{" in str(button.get("url") or ""):
                    return False
                if str(button.get("type") or "").upper() in {"COPY_CODE", "FLOW"}:
                    return False
    return True
    return False


def choose_template(templates):
    approved = [
        row for row in templates
        if str(row.get("status") or "").upper() == "APPROVED"
        and template_is_sendable_without_components(row)
    ]
    approved.sort(key=lambda row: (str(row.get("category") or ""), str(row.get("name") or "")))
    return approved[0] if approved else None


def rows_from_comparison(comparison):
    rows = []
    for waba in comparison.get("wabas", []):
        if waba.get("error"):
            continue
        for phone in waba.get("phones", []):
            meta = phone.get("meta") or {}
            local = phone.get("local") or {}
            platform_type = str(meta.get("platform_type") or local.get("platform_type") or "").upper()
            phone_number_id = str(phone.get("phone_number_id") or meta.get("id") or local.get("phone_number_id") or "")
            if not phone_number_id:
                continue
            rows.append(
                {
                    "waba_id": waba.get("waba_id"),
                    "waba_name": waba.get("name"),
                    "phone_number_id": phone_number_id,
                    "display_phone_number": meta.get("display_phone_number") or local.get("display_phone_number"),
                    "verified_name": meta.get("verified_name") or local.get("verified_name"),
                    "classification": phone.get("classification"),
                    "platform_type": platform_type,
                }
            )
    return rows


def secure_json(path, value):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)


def secure_csv(path, rows):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "waba_id",
                "waba_name",
                "phone_number_id",
                "display_phone_number",
                "verified_name",
                "platform_type",
                "classification",
                "attempt_type",
                "template_name",
                "status",
                "http_status",
                "message_id",
                "error",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Send a WhatsApp test message from each reachable ANK sender")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--to", required=True, help="Destination phone number, e.g. +917777018534")
    parser.add_argument("--waba-id", action="append", default=[], dest="waba_ids")
    parser.add_argument("--graph-version", default=DEFAULT_GRAPH_VERSION)
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv=None, *, password_reader=getpass.getpass):
    args = parse_args(argv)
    graph_token = os.getenv("META_ACCESS_TOKEN", "")
    email = os.getenv("ANK_ADMIN_EMAIL", "")
    password = os.getenv("ANK_ADMIN_PASSWORD", "")
    if not graph_token:
        raise ScriptError("META_ACCESS_TOKEN is required", 3)
    if not email:
        raise ScriptError("ANK_ADMIN_EMAIL is required", 3)
    if not password:
        password = password_reader("Django admin password: ")
    if not password:
        raise ScriptError("A Django admin password is required", 3)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_dir = Path(args.output_dir) if args.output_dir else Path("/tmp/ank-whatsapp-sender-test") / stamp
    report_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(report_dir, 0o700)

    hosted = HostedClient(args.base_url)
    user = hosted.login(email, password)
    preview = hosted.preview(graph_token, args.waba_ids)
    comparison = preview["comparison"]
    graph = GraphClient(graph_token, args.graph_version)
    target = norm_digits(args.to)
    results = []
    template_cache = {}

    for row in rows_from_comparison(comparison):
        result = {**row, "attempt_type": "", "template_name": "", "status": "skipped", "http_status": "", "message_id": "", "error": ""}
        if row["platform_type"] != "CLOUD_API":
            result["error"] = f"platform_type={row['platform_type'] or 'UNKNOWN'}"
            results.append(result)
            continue
        if row["classification"] == "local_only":
            result["error"] = "local_only_not_returned_by_meta"
            results.append(result)
            continue

        templates = template_cache.get(row["waba_id"])
        if templates is None:
            templates, error, status_code = graph.templates(row["waba_id"])
            if error:
                result["error"] = f"template_fetch_failed: {error}"
                result["http_status"] = status_code
                results.append(result)
                template_cache[row["waba_id"]] = []
                continue
            template_cache[row["waba_id"]] = templates

        selected_template = choose_template(template_cache[row["waba_id"]])
        if selected_template:
            result["attempt_type"] = "template"
            result["template_name"] = selected_template.get("name") or ""
            payload = {
                "messaging_product": "whatsapp",
                "to": target,
                "type": "template",
                "template": {
                    "name": selected_template["name"],
                    "language": {"code": selected_template.get("language") or "en_US"},
                    "components": [],
                },
            }
        else:
            result["attempt_type"] = "text"
            payload = {
                "messaging_product": "whatsapp",
                "to": target,
                "type": "text",
                "text": {
                    "body": (
                        f"ANK sender test from {row['verified_name'] or row['display_phone_number']} "
                        f"({row['phone_number_id']})"
                    )
                },
            }

        if args.dry_run:
            result["status"] = "dry_run"
            results.append(result)
            continue

        payload_response, error, status_code = graph.send(row["phone_number_id"], payload)
        result["http_status"] = status_code
        if error:
            result["status"] = "failed"
            result["error"] = json.dumps(error, sort_keys=True)[:1000]
        else:
            result["status"] = "sent"
            result["message_id"] = ((payload_response or {}).get("messages") or [{}])[0].get("id", "")
        results.append(result)

    secure_json(report_dir / "comparison.json", comparison)
    secure_json(report_dir / "send_results.json", results)
    secure_csv(report_dir / "send_results.csv", results)

    sent = sum(1 for row in results if row["status"] == "sent")
    failed = sum(1 for row in results if row["status"] == "failed")
    skipped = sum(1 for row in results if row["status"] == "skipped")
    print(f"Authenticated as {user.get('email', email)} ({user.get('role')})")
    print(f"Target: {target}")
    print(f"Results: sent={sent}, failed={failed}, skipped={skipped}, total={len(results)}")
    print(f"Reports: {report_dir}")
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ScriptError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(exc.exit_code)
