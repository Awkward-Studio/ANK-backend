from rest_framework import serializers
from Logistics.models.accomodation_models import Hotel


class HotelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hotel
        fields = ["id", "name", "types_of_rooms"]
