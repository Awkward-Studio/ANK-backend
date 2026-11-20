from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


@never_cache
@require_GET
def google_calendar_callback(request):
    if not request.GET:
        return JsonResponse(
            {"detail": "Start the Google Calendar connection from ANK."},
            status=400,
        )

    # Reserve the redirect URI while the authorization flow is being configured.
    # Never exchange a code until ANK can verify the originating session and state.
    return JsonResponse(
        {"detail": "Google Calendar connections are not enabled yet."},
        status=503,
    )
