import hashlib
import json
from collections.abc import Mapping

from django.db import transaction
from django.views.decorators.cache import never_cache
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from Staff.models import MeetingEventLink, TeamTask, User
from Departments.permissions import PermissionChecker


def owner_key(value):
    return " ".join(value.split()).casefold()


def unique_active_assignees(owners):
    owner_keys = {owner_key(owner) for owner in owners if owner.strip()}
    if not owner_keys:
        return {}

    exact = {}
    first_names = {}
    short_accounts = {}
    for user_id, name, email in User.objects.filter(is_active=True).values_list("pk", "name", "email"):
        name, email = owner_key(name), owner_key(email)
        for key in {name, email} & owner_keys:
            exact.setdefault(key, set()).add(user_id)

        email_handle, _, _ = email.partition("@")
        first_name = name.split(" ", 1)[0] or email_handle
        if first_name:
            first_names.setdefault(first_name, set()).add(user_id)
        if name and " " not in name:
            short_accounts.setdefault(name, set()).add(user_id)
        elif not name and email_handle:
            short_accounts.setdefault(email_handle, set()).add(user_id)

    resolved = {}
    for key in owner_keys:
        ids = exact.get(key)
        if ids is None:
            first_name, separator, _ = key.partition(" ")
            if separator and "@" not in key:
                possible = first_names.get(first_name, set())
                if len(possible) == 1 and possible == short_accounts.get(first_name):
                    ids = possible
        if ids and len(ids) == 1:
            resolved[key] = next(iter(ids))
    return resolved


def can_manage_tasks(user):
    return user.is_superuser or user.role in {"admin", "super_admin"}


class TaskSerializer(serializers.ModelSerializer):
    assignee = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(is_active=True), allow_null=True, required=False,
    )

    ank_event = serializers.SerializerMethodField()
    suggested_assignee = serializers.SerializerMethodField()

    def get_suggested_assignee(self, task):
        if task.status != TeamTask.Status.DRAFT or task.assignee_id:
            return None
        user_id = self.context.get("suggested_assignees", {}).get(owner_key(task.suggested_owner))
        return str(user_id) if user_id else None

    def get_ank_event(self, task):
        link = task.meeting_link
        accessible_ids = self.context.get("accessible_ids", set())
        if link and link.event_id in accessible_ids:
            return {"id": str(link.event_id), "name": link.event.name}
        return None

    class Meta:
        model = TeamTask
        fields = [
            "id", "title", "description", "suggested_owner", "status", "due_date",
            "assignee", "meeting_title", "notes_url", "ank_event", "suggested_assignee",
        ]
        read_only_fields = ["suggested_owner", "meeting_title", "notes_url"]

    def validate_status(self, value):
        if value == TeamTask.Status.DRAFT and self.instance.status != TeamTask.Status.DRAFT:
            raise serializers.ValidationError("An active task cannot return to drafts.")
        return value



class CreateTaskSerializer(TaskSerializer):
    request_id = serializers.UUIDField(write_only=True)

    class Meta(TaskSerializer.Meta):
        fields = (*TaskSerializer.Meta.fields, "request_id")

    def create(self, validated_data):
        user = self.context["user"]
        request_id = validated_data.pop("request_id")
        task, created = TeamTask.objects.get_or_create(
            source_key=source_key("manual-task", str(user.pk), str(request_id)),
            defaults={**validated_data, "created_by": user},
        )
        self.created = created
        return task

    def validate_status(self, value):
        if value == TeamTask.Status.DRAFT:
            raise serializers.ValidationError("Choose a board status.")
        return value


def step_key(step):
    values = [" ".join(step[field].split()).casefold() for field in ("owner", "title", "description")]
    return hashlib.sha256(json.dumps(values).encode()).hexdigest()


def source_key(calendar_id, event_id, key):
    return hashlib.sha256(json.dumps([calendar_id, event_id, key]).encode()).hexdigest()


def mark_saved_steps(calendar_id, event_id, steps):
    keys = {step_key(step): source_key(calendar_id, event_id, step_key(step)) for step in steps}
    saved = dict(TeamTask.objects.filter(source_key__in=keys.values(), meeting_link__isnull=False).values_list("source_key", "status"))
    for step in steps:
        step["id"] = step_key(step)
        step["task_status"] = saved.get(keys[step["id"]])
        step["saved"] = step["task_status"] is not None


class ImportSerializer(serializers.Serializer):
    steps = serializers.ListField(
        child=serializers.RegexField(r"^[a-f0-9]{64}$"), min_length=1, max_length=100,
    )


def save_meeting_steps(user, calendar_id, event_id, document, selected):
    candidates = {step_key(step): step for step in document.get("suggested_steps", [])}
    if not set(selected) <= candidates.keys():
        raise ValidationError("The notes have changed. Reload the document and select the steps again.")
    assignees = unique_active_assignees(candidates[key]["owner"] for key in selected)
    with transaction.atomic():
        link, _ = MeetingEventLink.objects.get_or_create(calendar_id=calendar_id, meeting_id=event_id)
        tasks = []
        for key in dict.fromkeys(selected):
            step = candidates[key]
            task, _ = TeamTask.objects.get_or_create(
                source_key=source_key(calendar_id, event_id, key),
                defaults={
                    "meeting_link": link,
                    "title": step["title"][:255],
                    "description": step["description"],
                    "suggested_owner": step["owner"][:255],
                    "assignee_id": assignees.get(owner_key(step["owner"])),
                    "created_by": user,
                    "meeting_title": (document.get("meeting_title") or document["title"])[:500],
                    "notes_url": document["url"][:500],
                },
            )
            if task.meeting_link_id is None:
                task.meeting_link = link
                task.save(update_fields=["meeting_link"])
            tasks.append(task)
    return TaskSerializer(tasks, many=True).data


@never_cache
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def team_tasks(request):
    manager = can_manage_tasks(request.user)
    if request.method == "POST":
        if not manager:
            raise PermissionDenied()
        serializer = CreateTaskSerializer(data=request.data, context={"user": request.user})
        serializer.is_valid(raise_exception=True)
        task = serializer.save(status=serializer.validated_data.get("status", TeamTask.Status.TODO))
        return Response(
            TaskSerializer(task).data, status=status.HTTP_201_CREATED if serializer.created else status.HTTP_200_OK,
        )
    tasks = TeamTask.objects.select_related("meeting_link__event")
    staff = []
    if manager:
        staff = [
            {"id": str(user.pk), "name": user.name or user.email}
            for user in User.objects.filter(is_active=True).order_by("name", "email")
        ]
    else:
        tasks = tasks.filter(assignee=request.user).exclude(status=TeamTask.Status.DRAFT)
    tasks = list(tasks)
    event_ids = {task.meeting_link.event_id for task in tasks if task.meeting_link_id}
    accessible_ids = set(PermissionChecker.get_user_accessible_events(request.user).filter(pk__in=event_ids).values_list("pk", flat=True))
    suggestions = unique_active_assignees(
        task.suggested_owner for task in tasks if task.status == TeamTask.Status.DRAFT and not task.assignee_id
    )
    return Response({
        "can_manage": manager,
        "users": staff,
        "tasks": TaskSerializer(tasks, many=True, context={"accessible_ids": accessible_ids, "suggested_assignees": suggestions}).data,
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
    event_id = task.meeting_link.event_id if task.meeting_link_id else None
    visible_ids = set(PermissionChecker.get_user_accessible_events(request.user).filter(pk=event_id).values_list("pk", flat=True)) if event_id else set()
    return Response(TaskSerializer(task, context={"accessible_ids": visible_ids}).data)
