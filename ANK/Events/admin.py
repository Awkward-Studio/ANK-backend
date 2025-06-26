from django.contrib import admin
from Events.models.event_model import Event
from Events.models.session_model import Session
from Events.models.event_registration_model import EventRegistration
from Events.models.session_registration import SessionRegistration

# Register your models here.
admin.site.register(Event)
admin.site.register(Session)
admin.site.register(EventRegistration)
admin.site.register(SessionRegistration)
