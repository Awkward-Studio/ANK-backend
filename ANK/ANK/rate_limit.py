from __future__ import annotations

from dataclasses import dataclass
from time import time

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse


@dataclass(frozen=True)
class LimitRule:
    prefix: str
    limit: int
    window: int
    methods: tuple[str, ...] | None = None


class RateLimitMiddleware:
    """
    Lightweight IP rate limiting for public/sensitive Django function views.

    DRF throttling covers APIView/api_view endpoints. This middleware covers
    csrf-exempt webhook views and public token URLs that bypass DRF throttles.
    For multi-instance production, configure Django CACHES to use Redis/shared cache.
    """

    DEFAULT_RULES = (
        LimitRule("/api/auth/login/", 10, 60, ("POST",)),
        LimitRule("/api/auth/register/", 5, 60, ("POST",)),
        LimitRule("/api/auth/refresh/", 30, 60, ("POST",)),
        LimitRule("/api/webhooks/", 120, 60, None),
        LimitRule("/api/internal/resolve-wa/", 120, 60, None),
        LimitRule("/api/public/opt-in/", 30, 60, None),
        LimitRule("/api/manpower/public/", 60, 60, None),
        LimitRule("/api/csrf/", 60, 60, None),
    )

    def __init__(self, get_response):
        self.get_response = get_response
        self.enabled = getattr(settings, "RATE_LIMIT_ENABLED", True)
        self.rules = getattr(settings, "RATE_LIMIT_RULES", self.DEFAULT_RULES)

    def __call__(self, request):
        if self.enabled:
            rule = self._match_rule(request)
            if rule and self._is_limited(request, rule):
                return JsonResponse(
                    {"detail": "Too many requests. Please try again shortly."},
                    status=429,
                )
        return self.get_response(request)

    def _match_rule(self, request):
        path = request.path
        method = request.method.upper()
        for rule in self.rules:
            if path.startswith(rule.prefix) and (rule.methods is None or method in rule.methods):
                return rule
        return None

    def _client_ip(self, request) -> str:
        forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "unknown")

    def _is_limited(self, request, rule: LimitRule) -> bool:
        now = int(time())
        bucket = now // rule.window
        key = f"rl:{rule.prefix}:{request.method}:{self._client_ip(request)}:{bucket}"
        added = cache.add(key, 1, timeout=rule.window + 5)
        if added:
            return False
        try:
            count = cache.incr(key)
        except ValueError:
            cache.set(key, 1, timeout=rule.window + 5)
            return False
        return count > rule.limit
