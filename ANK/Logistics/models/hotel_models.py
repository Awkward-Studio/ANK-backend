from django.db import models
import uuid
from django.db.models import JSONField


class Hotel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    types_of_rooms = JSONField(default=list, blank=True)

    def __str__(self):
        return self.name
