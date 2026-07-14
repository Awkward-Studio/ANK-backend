import hmac

from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from MessageTemplates.permissions import IsWhatsAppAdmin
from MessageTemplates.services.hosted_reconciliation import (
    GRAPH_VERSION,
    apply_comparison,
    build_comparison,
    hosted_snapshot,
)


class ReconciliationRequestSerializer(serializers.Serializer):
    graph_api_version = serializers.ChoiceField(choices=[GRAPH_VERSION], default=GRAPH_VERSION)
    access_token = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        min_length=20,
        max_length=4096,
    )
    waba_ids = serializers.ListField(
        child=serializers.CharField(max_length=100), required=False, default=list
    )


class ReconciliationApplySerializer(ReconciliationRequestSerializer):
    comparison_digest = serializers.RegexField(r"^[a-f0-9]{64}$")


class ReconciliationBaseView(APIView):
    permission_classes = [IsWhatsAppAdmin]
    throttle_scope = "whatsapp_reconciliation"


class HostedReconciliationSnapshotView(ReconciliationBaseView):
    def get(self, request):
        waba_ids = request.query_params.getlist("waba_id")
        return Response(hosted_snapshot(waba_ids))


class HostedReconciliationPreviewView(ReconciliationBaseView):
    def post(self, request):
        serializer = ReconciliationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        comparison, digest = build_comparison(data["access_token"], data["waba_ids"])
        return Response({"comparison": comparison, "comparison_digest": digest})


class HostedReconciliationApplyView(ReconciliationBaseView):
    def post(self, request):
        serializer = ReconciliationApplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        comparison, digest = build_comparison(data["access_token"], data["waba_ids"])
        if not hmac.compare_digest(digest, data["comparison_digest"]):
            return Response(
                {
                    "error": "Meta or hosted data changed after preview; run preview again",
                    "expected_digest": data["comparison_digest"],
                    "current_digest": digest,
                },
                status=status.HTTP_409_CONFLICT,
            )
        result = apply_comparison(comparison)
        return Response(
            {
                "comparison_digest": digest,
                "comparison": comparison,
                "apply_result": result,
            },
            status=status.HTTP_200_OK,
        )
