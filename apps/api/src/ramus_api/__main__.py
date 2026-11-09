"""``python -m ramus_api`` serves the API on 127.0.0.1:{RAMUS_API_PORT}."""

import uvicorn

from ramus_api.main import create_app
from ramus_api.settings import Settings

HOST = "127.0.0.1"


def main() -> None:
    settings = Settings()
    uvicorn.run(create_app(settings), host=HOST, port=settings.api_port)


if __name__ == "__main__":
    main()
