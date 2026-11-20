import hashlib
import json
from collections.abc import Mapping

from django.db import transaction
from django.views.decorators.cache import never_cache
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from Staff.models import TeamTask, User


def can_manage_tasks(user):
    return user.is_superuser or user.role in {"admin", "super_admin"}


class TaskSerializer(serializers.ModelSerializer):
    assignee = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(is_active=True), allow_null=True, required=False,
    )

    class Meta:
        model = TeamTask
        fields = [
            "id", "title", "description", "suggested_owner", "status", "due_date",
            "assignee", "meeting_title", "notes_url",
        ]
        read_only_fields = ["suggested_owner", "meeting_title", "notes_url"]

    def validate_status(self, value):
        if value == TeamTask.Status.DRAFT and self.instance.status != TeamTask.Status.DRAFT:
            raise serializers.ValidationError("An active task cannot return to drafts.")
        return value


def step_key(step):
    values = [" ".join(step[field].split()).casefold() for field in ("owner", "title", "description")]
    return hashlib.sha256(json.dumps(values).encode()).hexdigest()


def source_key(calendar_id, event_id, key):
    return hashlib.sha256(json.dumps([calendar_id, event_id, key]).encode()).hexdigest()


def mark_saved_steps(calendar_id, event_id, steps):
    keys = {step_key(step): source_key(calendar_id, event_id, step_key(step)) for step in steps}
    saved = set(TeamTask.objects.filter(source_key__in=keys.values()).values_list("source_key", flat=True))
    for step in steps:
        step["id"] = step_key(step)
        step["saved"] = keys[step["id"]] in saved


class ImportSerializer(serializers.Serializer):
    steps = serializers.ListField(
        child=serializers.RegexField(r"^[a-f0-9]{64}$"), min_length=1, max_length=100,
    )


def save_meeting_steps(user, calendar_id, event_id, document, selected):
    candidates = {step_key(step): step for step in document.get("suggested_steps", [])}
    if not set(selected) <= candidates.keys():
        raise ValidationError("The notes have changed. Reload the document and select the steps again.")
    with transaction.atomic():
        tasks = []
        for key in dict.fromkeys(selected):
            step = candidates[key]
            task, _ = TeamTask.objects.get_or_create(
                source_key=source_key(calendar_id, event_id, key),
                defaults={
                    "title": step["title"][:255],
                    "description": step["description"],
                    "suggested_owner": step["owner"][:255],
                    "created_by": user,
                    "meeting_title": (document.get("meeting_title") or document["title"])[:500],
                    "notes_url": document["url"][:500],
                },
            )
            tasks.append(task)
    return TaskSerializer(tasks, many=True).data


@never_cache
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def team_tasks(request):
    manager = can_manage_tasks(request.user)
    tasks = TeamTask.objects.all()
    staff = []
    if manager:
        staff = [
            {"id": str(user.pk), "name": user.name or user.email}
            for user in User.objects.filter(is_active=True).order_by("name", "email")
        ]
    else:
        tasks = tasks.filter(assignee=request.user).exclude(status=TeamTask.Status.DRAFT)
    return Response({
        "can_manage": manager,
        "users": staff,
        "tasks": TaskSerializer(tasks, many=True).data,
    })


@never_cache
@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def team_task(request, pk):
    with transaction.atomic():
        tasks = TeamTask.objects.select_for_update()
        if not isinstance(request.data, Mapping):
            raise ValidationError("Provide task fields as an object.")
        if not can_manage_tasks(request.user):
            if set(request.data) != {"status"} or request.data["status"] == TeamTask.Status.DRAFT:
                raise PermissionDenied()
            tasks = tasks.filter(assignee=request.user).exclude(status=TeamTask.Status.DRAFT)
        task = get_object_or_404(tasks, pk=pk)
        serializer = TaskSerializer(task, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
    return Response(serializer.data)
