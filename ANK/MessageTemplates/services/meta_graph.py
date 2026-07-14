import logging
import time
from typing import Any, Dict, Iterable, Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class MetaGraphError(Exception):
    def __init__(self, message, *, status_code=None, code=None, subcode=None, fbtrace_id=None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.subcode = subcode
        self.fbtrace_id = fbtrace_id


class MetaAuthenticationError(MetaGraphError):
    pass


class MetaPermissionError(MetaGraphError):
    pass


class MetaRateLimitError(MetaGraphError):
    pass


class MetaNotFoundError(MetaGraphError):
    pass


class MetaValidationError(MetaGraphError):
    pass


class MetaTemporaryError(MetaGraphError):
    pass


class MetaGraphClient:
    def __init__(self, access_token: str, *, session=None, timeout=(5, 20)):
        if not access_token:
            raise MetaAuthenticationError("No Meta access token is configured")
        self.access_token = access_token
        self.session = session or requests.Session()
        self.timeout = timeout
        self.base_url = (
            f"{settings.META_GRAPH_API_BASE_URL}/{settings.META_GRAPH_API_VERSION}"
        )

    def _raise_error(self, response):
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        error = payload.get("error") or {}
        message = error.get("error_user_msg") or error.get("message") or (
            f"Meta returned HTTP {response.status_code}"
        )
        code = error.get("code")
        subcode = error.get("error_subcode")
        kwargs = {
            "status_code": response.status_code,
            "code": code,
            "subcode": subcode,
            "fbtrace_id": error.get("fbtrace_id"),
        }
        if response.status_code == 429 or code in {4, 17, 32, 613}:
            raise MetaRateLimitError(message, **kwargs)
        if code == 190 or response.status_code == 401:
            raise MetaAuthenticationError(message, **kwargs)
        if code in {10, 200} or response.status_code == 403:
            raise MetaPermissionError(message, **kwargs)
        if response.status_code == 404 or subcode in {33, 2018001}:
            raise MetaNotFoundError(message, **kwargs)
        if response.status_code >= 500 or error.get("is_transient"):
            raise MetaTemporaryError(message, **kwargs)
        raise MetaValidationError(message, **kwargs)

    def request(self, method: str, path_or_url: str, *, params=None, json=None):
        url = path_or_url if path_or_url.startswith("http") else f"{self.base_url}/{path_or_url.lstrip('/')}"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        for attempt in range(3):
            try:
                response = self.session.request(
                    method,
                    url,
                    params=params,
                    json=json,
                    headers=headers,
                    timeout=self.timeout,
                )
            except requests.RequestException as exc:
                if attempt == 2:
                    raise MetaTemporaryError(str(exc)) from exc
                time.sleep(0.2 * (2**attempt))
                continue
            if response.ok:
                try:
                    return response.json()
                except ValueError as exc:
                    raise MetaGraphError("Meta returned a non-JSON response") from exc
            try:
                self._raise_error(response)
            except (MetaRateLimitError, MetaTemporaryError):
                if attempt < 2:
                    time.sleep(0.2 * (2**attempt))
                    continue
                raise
        raise MetaTemporaryError("Meta request failed after retries")

    def get(self, path_or_url: str, *, params=None):
        return self.request("GET", path_or_url, params=params)

    def post(self, path_or_url: str, *, params=None, json=None):
        return self.request("POST", path_or_url, params=params, json=json)

    def get_all(self, path: str, *, params=None) -> list[dict]:
        items = []
        url = path
        next_params = params
        while url:
            payload = self.get(url, params=next_params)
            items.extend(payload.get("data") or [])
            url = (payload.get("paging") or {}).get("next")
            next_params = None
        return items

    def list_phone_numbers(self, waba_id: str) -> list[dict]:
        return self.get_all(
            f"{waba_id}/phone_numbers",
            params={
                "fields": "id,display_phone_number,verified_name,quality_rating",
                "limit": 100,
            },
        )

    def get_phone_number(self, phone_number_id: str, fields: Iterable[str]) -> Dict[str, Any]:
        return self.get(phone_number_id, params={"fields": ",".join(fields)})

    def list_templates(self, waba_id: str, *, fields: Optional[str] = None) -> list[dict]:
        params = {"limit": 100}
        if fields:
            params["fields"] = fields
        return self.get_all(f"{waba_id}/message_templates", params=params)

    def create_template(self, waba_id: str, payload: dict) -> dict:
        return self.post(f"{waba_id}/message_templates", json=payload)

    def subscribe_waba(self, waba_id: str) -> dict:
        return self.post(f"{waba_id}/subscribed_apps")
