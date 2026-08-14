from fastapi import Request

from controllers.utils.bootstrap.dependencies import ApplicationContainer


def get_container(request: Request) -> ApplicationContainer:
    return request.app.state.container
