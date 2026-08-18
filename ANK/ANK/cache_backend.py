"""
Resilient cache backend that wraps RedisCache and falls back to
LocMemCache when Redis is unreachable.

This prevents 500 errors across the entire application (DRF throttling,
rate-limit middleware, permissions caching, etc.) if the Redis connection
is temporarily unavailable.
"""

import logging

from django.core.cache.backends.locmem import LocMemCache
from django.core.cache.backends.redis import RedisCache

logger = logging.getLogger(__name__)


class ResilientRedisCache(RedisCache):
    """
    A Redis cache backend that silently falls back to an in-process
    LocMemCache when Redis is unreachable, instead of raising exceptions.
    """

    def __init__(self, server, params):
        super().__init__(server, params)
        self._fallback = LocMemCache("resilient-fallback", {})
        self._warned = False

    def _warn_once(self, method, exc):
        if not self._warned:
            logger.warning(
                "Redis cache unavailable (%s in %s); using in-memory fallback. "
                "Rate limiting and caching will not be shared across processes.",
                exc.__class__.__name__,
                method,
                exc_info=True,
            )
            self._warned = True

    # -- read operations --------------------------------------------------

    def get(self, key, default=None, version=None):
        try:
            return super().get(key, default, version)
        except Exception as exc:
            self._warn_once("get", exc)
            return self._fallback.get(key, default, version)

    def get_many(self, keys, version=None):
        try:
            return super().get_many(keys, version)
        except Exception as exc:
            self._warn_once("get_many", exc)
            return self._fallback.get_many(keys, version)

    def has_key(self, key, version=None):
        try:
            return super().has_key(key, version)
        except Exception as exc:
            self._warn_once("has_key", exc)
            return self._fallback.has_key(key, version)

    # -- write operations -------------------------------------------------

    def set(self, key, value, timeout=None, version=None):
        try:
            return super().set(key, value, timeout, version)
        except Exception as exc:
            self._warn_once("set", exc)
            return self._fallback.set(key, value, timeout, version)

    def add(self, key, value, timeout=None, version=None):
        try:
            return super().add(key, value, timeout, version)
        except Exception as exc:
            self._warn_once("add", exc)
            return self._fallback.add(key, value, timeout, version)

    def set_many(self, mapping, timeout=None, version=None):
        try:
            return super().set_many(mapping, timeout, version)
        except Exception as exc:
            self._warn_once("set_many", exc)
            return self._fallback.set_many(mapping, timeout, version)

    # -- mutate operations ------------------------------------------------

    def incr(self, key, delta=1, version=None):
        try:
            return super().incr(key, delta, version)
        except Exception as exc:
            self._warn_once("incr", exc)
            return self._fallback.incr(key, delta, version)

    def delete(self, key, version=None):
        try:
            return super().delete(key, version)
        except Exception as exc:
            self._warn_once("delete", exc)
            return self._fallback.delete(key, version)

    def delete_many(self, keys, version=None):
        try:
            return super().delete_many(keys, version)
        except Exception as exc:
            self._warn_once("delete_many", exc)
            return self._fallback.delete_many(keys, version)

    def clear(self):
        try:
            return super().clear()
        except Exception as exc:
            self._warn_once("clear", exc)
            return self._fallback.clear()
