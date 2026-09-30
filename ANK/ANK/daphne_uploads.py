"""Avoid Twisted's duplicate in-memory form parsing in Daphne 4.2.1.

Django parses form data with its own upload handlers. Twisted's default parser
reads the entire multipart body and creates additional copies before Django's
disk-backed handlers can run. Daphne does not use the resulting request.args.
"""

from daphne import http_protocol


def configure_daphne_uploads():
    # Install before Daphne creates any request objects. Keep this idempotent
    # for ASGI reloads and leave Django's normal form parsing unchanged.
    if getattr(http_protocol.WebRequest, "django_parses_form_data", False):
        return

    class DjangoWebRequest(http_protocol.WebRequest):
        django_parses_form_data = True

        def __init__(self, *args, **kwargs):
            kwargs["parsePOSTFormSubmission"] = False
            super().__init__(*args, **kwargs)

    http_protocol.WebRequest = DjangoWebRequest
