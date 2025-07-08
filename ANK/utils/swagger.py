from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiTypes,
    extend_schema,
    extend_schema_view,
)

# Map string types to OpenApiTypes
TYPE_MAP = {
    "str": OpenApiTypes.STR,
    "int": OpenApiTypes.INT,
    "bool": OpenApiTypes.BOOL,
    "float": OpenApiTypes.FLOAT,
    "date": OpenApiTypes.DATE,
    "uuid": OpenApiTypes.UUID,
    "email": OpenApiTypes.EMAIL,
}


def query_param(name, type_: str, required=False, description=""):
    return OpenApiParameter(
        name=name,
        type=TYPE_MAP.get(type_.lower(), OpenApiTypes.STR),
        location=OpenApiParameter.QUERY,
        required=required,
        description=description,
    )


def doc_list(response=None, parameters=None, description="", tags=None):
    return extend_schema(
        responses=response,
        parameters=parameters or [],
        description=description,
        tags=tags or [],
    )


def doc_create(request=None, response=None, description="", tags=None):
    return extend_schema(
        request=request, responses=response, description=description, tags=tags or []
    )


def doc_update(request=None, response=None, description="", tags=None):
    return extend_schema(
        request=request, responses=response, description=description, tags=tags or []
    )


def doc_destroy(response=None, description="", tags=None):
    return extend_schema(responses=response, description=description, tags=tags or [])


def doc_retrieve(response=None, description="", tags=None):
    return extend_schema(responses=response, description=description, tags=tags or [])


def doc_viewset(docs: dict):
    """
    DRY wrapper over extend_schema_view for class-based ViewSets.

    Example:
    @doc_viewset({
        "list": doc_list(...),
        "create": doc_create(...),
    })
    class MyViewSet(...):
        ...
    """
    return extend_schema_view(**docs)


def document_api_view(method_docs: dict):
    """
    Apply drf-spectacular Swagger decorators to APIView methods.
    method_docs keys = method names ('get','post','put','delete'),
    values = one of the doc_*() decorators.
    """

    def decorator(cls):
        for method_name, doc_decorator in method_docs.items():
            if hasattr(cls, method_name):
                setattr(cls, method_name, doc_decorator(getattr(cls, method_name)))
        return cls

    return decorator
