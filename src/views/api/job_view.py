from views.api.responses import JobResponse


def render_job(data: dict[str, object]) -> JobResponse:
    return JobResponse.model_validate(data)
