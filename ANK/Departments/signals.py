"""
Signals for cache invalidation when permissions change.
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from Departments.models import ModelPermission, EventDepartmentStaffAssignment
from Departments.permissions import invalidate_permission_cache


@receiver(post_save, sender=ModelPermission)
def invalidate_cache_on_permission_save(sender, instance, **kwargs):
    """Invalidate cache when ModelPermission is created or updated."""
    invalidate_permission_cache(sender, instance, **kwargs)


@receiver(post_delete, sender=ModelPermission)
def invalidate_cache_on_permission_delete(sender, instance, **kwargs):
    """Invalidate cache when ModelPermission is deleted."""
    invalidate_permission_cache(sender, instance, **kwargs)


@receiver(post_save, sender=EventDepartmentStaffAssignment)
def invalidate_cache_on_assignment_save(sender, instance, **kwargs):
    """Invalidate cache when EventDepartmentStaffAssignment changes (affects event access)."""
    # Invalidate all permission caches for this user + event_department
    from django.core.cache import cache
    cache_key = f"perms:{instance.user.id}:{instance.event_department.id}"
    cache.delete(cache_key)


@receiver(post_delete, sender=EventDepartmentStaffAssignment)
def invalidate_cache_on_assignment_delete(sender, instance, **kwargs):
    """Invalidate cache when EventDepartmentStaffAssignment is deleted."""
    from django.core.cache import cache
    cache_key = f"perms:{instance.user.id}:{instance.event_department.id}"
    cache.delete(cache_key)
