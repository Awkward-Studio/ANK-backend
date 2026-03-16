from django.http import JsonResponse
from django.conf import settings
from django.urls import resolve, Resolver404
import traceback

class ApiSlashMiddleware:
    """
    Handle missing trailing slashes for /api/ requests internally 
    to avoid 307/301 redirects which can strip Authorization headers.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        original_path = request.path_info
        
        if request.path.startswith('/api/') and not request.path.endswith('/'):
            path_with_slash = original_path + '/'
            try:
                # Internally update the path if it resolves with a slash
                resolve(path_with_slash)
                request.path_info = path_with_slash
                print(f"INTERNAL URL REWRITE: {request.method} {original_path} -> {path_with_slash} (No Redirect)")
            except:
                pass
        
        return self.get_response(request)

class JsonErrorMiddleware:
    """
    Ensure that errors and redirects for /api/ paths are logged and 
    always returned as JSON (no HTML debug pages).
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Log redirects for /api/ paths to help debug remaining issues
        if request.path.startswith('/api/') and 300 <= response.status_code < 400:
            print(f"REDIRECT STILL OCCURRING: {request.method} {request.path} -> {response.get('Location', 'Unknown')} (Status: {response.status_code})")

        # Force JSON for errors on /api/ paths
        if request.path.startswith('/api/') and response.status_code >= 400:
            content_type = response.get('Content-Type', '')
            if 'application/json' in content_type:
                return response
            
            data = {
                "detail": "Not Found" if response.status_code == 404 else "Server Error",
                "status_code": response.status_code,
                "path": request.path
            }
            
            if settings.DEBUG and response.status_code == 500:
                data["exception"] = str(getattr(response, 'context_data', {}).get('exception', 'Unknown'))
            
            return JsonResponse(data, status=response.status_code)
            
        return response
