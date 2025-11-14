from rest_framework import serializers
from utilities.models.vendor_model import Vendor


class VendorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = [
            "id",
            "name",
            "service_category",
            "contact_name",
            "contact_phone",
            "email",
            "city",
            "country",
            "gst_number",
            "website",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]
