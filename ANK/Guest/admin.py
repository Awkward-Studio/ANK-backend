from django.contrib import admin

from .models import Guest, GuestField

# Register your models here.
admin.site.register(Guest)
admin.site.register(GuestField)
