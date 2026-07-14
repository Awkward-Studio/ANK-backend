from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from MessageTemplates.models import WhatsAppBusinessAccount
from MessageTemplates.permissions import IsWhatsAppAdminOrInternalService
from MessageTemplates.services.meta_graph import MetaGraphClient, MetaGraphError


class MetaTemplateListCreateView(APIView):
    permission_classes = [IsWhatsAppAdminOrInternalService]

    def _client(self, waba_id):
        waba = get_object_or_404(WhatsAppBusinessAccount, waba_id=waba_id)
        token = waba.get_token()
        if not token:
            phone = waba.phone_numbers.first()
            token = phone.get_access_token() if phone else ""
        return waba, MetaGraphClient(token)

    @staticmethod
    def _error(error):
        return Response(
            {
                "error": str(error),
                "meta_error_code": error.code,
                "meta_error_subcode": error.subcode,
                "fbtrace_id": error.fbtrace_id,
            },
            status=error.status_code if error.status_code in {400, 401, 403, 404, 429} else 502,
        )

    def get(self, request, waba_id):
        try:
            _, client = self._client(waba_id)
            templates = client.list_templates(waba_id)
            return Response({"templates": templates, "waba_id": waba_id})
        except MetaGraphError as error:
            return self._error(error)

    def post(self, request, waba_id):
        required = {"name", "category", "language", "components"}
        if not required.issubset(request.data):
            return Response(
                {"error": "name, category, language, and components are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        payload = {key: request.data[key] for key in required}
        try:
            _, client = self._client(waba_id)
            result = client.create_template(waba_id, payload)
            return Response({"success": True, "data": result}, status=status.HTTP_201_CREATED)
        except MetaGraphError as error:
            return self._error(error)
