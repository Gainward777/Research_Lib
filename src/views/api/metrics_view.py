from fastapi import Response


def render_metrics(
    payload: bytes,
    content_type: str,
    *,
    status_code: int = 200,
    authenticate: bool = False,
) -> Response:
    headers = {"Cache-Control": "no-store"}
    if authenticate:
        headers["WWW-Authenticate"] = "Bearer"
    headers["Content-Type"] = content_type
    return Response(
        content=payload,
        status_code=status_code,
        headers=headers,
        media_type=None,
    )
