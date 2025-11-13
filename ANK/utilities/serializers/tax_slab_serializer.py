from rest_framework import serializers
from utilities.models.tax_slab_model import TaxSlab


class TaxSlabSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxSlab
        fields = "__all__"
