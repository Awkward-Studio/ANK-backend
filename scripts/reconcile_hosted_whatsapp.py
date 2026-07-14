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
CONFIRM_TEXT = "APPLY_META_STATUS_UPDATES"


class ScriptError(Exception):
    def __init__(self, message, exit_code=5):
        super().__init__(message)
        self.exit_code = exit_code


def validate_base_url(value):
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ScriptError("The hosted API URL must be an HTTPS URL without embedded credentials", 3)
    return value.rstrip("/")


def secure_json(path, value):
    payload = json.dumps(value, indent=2, sort_keys=True, default=str).encode()
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(payload)


def secure_csv(path, comparison):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "waba_id",
                "waba_name",
                "classification",
                "phone_number_id",
                "display_phone_number",
                "differences",
                "unavailable_fields",
            ],
        )
        writer.writeheader()
        for waba in comparison.get("wabas", []):
            for row in waba.get("phones", []):
                local = row.get("local") or {}
                meta = row.get("meta") or {}
                writer.writerow(
                    {
                        "waba_id": waba.get("waba_id"),
                        "waba_name": waba.get("name"),
                        "classification": row.get("classification"),
                        "phone_number_id": row.get("phone_number_id"),
                        "display_phone_number": local.get("display_phone_number") or meta.get("display_phone_number"),
                        "differences": json.dumps(row.get("differences") or {}, sort_keys=True),
                        "unavailable_fields": ",".join(row.get("unavailable_fields") or []),
                    }
                )


class HostedApiClient:
    def __init__(self, base_url, session=None):
        self.base_url = validate_base_url(base_url)
        self.hostname = urlparse(self.base_url).hostname
        self.session = session or requests.Session()
        self.jwt = None

    def _request(self, method, path, **kwargs):
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
            raise ScriptError(f"Hosted API request failed: {exc.__class__.__name__}", 3) from exc
        if 300 <= response.status_code < 400:
            location = response.headers.get("Location", "")
            redirected_host = urlparse(urljoin(self.base_url, location)).hostname
            if redirected_host != self.hostname:
                raise ScriptError("Hosted API attempted to redirect to another hostname", 3)
            raise ScriptError("Unexpected hosted API redirect; verify the URL includes the correct path", 3)
        try:
            data = response.json()
        except ValueError as exc:
            raise ScriptError(f"Hosted API returned non-JSON HTTP {response.status_code}", 3) from exc
        if not response.ok:
            detail = data.get("detail") or data.get("error") or f"HTTP {response.status_code}"
            exit_code = 3 if response.status_code in {400, 401, 403} else 5
            raise ScriptError(f"Hosted API rejected the request: {detail}", exit_code)
        return data

    def login(self, email, password):
        data = self._request("POST", "/api/auth/login/", json={"email": email, "password": password})
        user = data.get("user") or {}
        if user.get("role") not in {"admin", "super_admin"}:
            raise ScriptError("The account is not an admin or super admin", 3)
        self.jwt = (data.get("tokens") or {}).get("access")
        if not self.jwt:
            raise ScriptError("Login succeeded without a JWT access token", 3)
        return user

    def snapshot(self, waba_ids):
        params = [("waba_id", value) for value in waba_ids]
        return self._request("GET", "/api/whatsapp/reconciliation/snapshot/", params=params)

    def preview(self, graph_token, waba_ids):
        return self._request(
            "POST",
            "/api/whatsapp/reconciliation/preview/",
            json={"graph_api_version": "v25.0", "access_token": graph_token, "waba_ids": waba_ids},
        )

    def apply(self, graph_token, waba_ids, digest):
        return self._request(
            "POST",
            "/api/whatsapp/reconciliation/apply/",
            json={"graph_api_version": "v25.0", "access_token": graph_token, "waba_ids": waba_ids, "comparison_digest": digest},
        )


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Cross-check hosted ANK WhatsApp records against Meta Graph API v25.0")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--waba-id", action="append", default=[], dest="waba_ids")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--output-dir", default="")
    return parser.parse_args(argv)


def mask(value):
    value = str(value or "")
    return value if len(value) <= 4 else f"{'*' * max(0, len(value) - 4)}{value[-4:]}"


def main(argv=None, *, session=None, password_reader=getpass.getpass):
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
    if args.apply and args.confirm != CONFIRM_TEXT:
        raise ScriptError(f"Apply requires --confirm {CONFIRM_TEXT}", 5)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_dir = Path(args.output_dir) if args.output_dir else Path("/tmp/ank-whatsapp-reconciliation") / stamp
    report_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(report_dir, 0o700)

    client = HostedApiClient(args.base_url, session=session)
    user = client.login(email, password)
    snapshot = client.snapshot(args.waba_ids)
    preview = client.preview(graph_token, args.waba_ids)
    comparison = preview["comparison"]
    digest = preview["comparison_digest"]
    secure_json(report_dir / "hosted_snapshot.json", snapshot)
    secure_json(report_dir / "summary.json", {"comparison_digest": digest, "comparison": comparison})
    secure_csv(report_dir / "phone_comparison.csv", comparison)
    errors = [{"waba_id": row.get("waba_id"), "error": row.get("error")} for row in comparison.get("wabas", []) if row.get("error")]
    secure_json(report_dir / "waba_errors.json", errors)

    summary = comparison.get("summary", {})
    print(f"Authenticated as {user.get('email', email)} ({user.get('role')})")
    print(f"Graph API: {comparison.get('graph_api_version')}")
    print(f"WABAs checked: {len(comparison.get('wabas', []))}")
    for key in ["exact_match", "field_mismatch", "partial_meta_data", "local_only", "meta_only", "waba_access_error"]:
        print(f"{key}: {summary.get(key, 0)}")
    print(f"Comparison digest: {digest}")
    print(f"Reports: {report_dir}")
    for waba in comparison.get("wabas", []):
        if waba.get("error"):
            print(f"WABA {mask(waba.get('waba_id'))}: ERROR {waba['error'].get('message')}")

    if args.apply:
        if errors:
            raise ScriptError("Apply was blocked because preview contains WABA access errors", 4)
        apply_result = client.apply(graph_token, args.waba_ids, digest)
        secure_json(report_dir / "apply_result.json", apply_result)
        changed = (apply_result.get("apply_result") or {}).get("changed_count", 0)
        skipped = (apply_result.get("apply_result") or {}).get("skipped_count", 0)
        print(f"Applied: changed={changed}, skipped={skipped}")
        return 0

    if errors:
        return 4
    discrepancy_count = sum(summary.get(key, 0) for key in ["field_mismatch", "partial_meta_data", "local_only", "meta_only"])
    return 2 if discrepancy_count else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ScriptError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(exc.exit_code)
