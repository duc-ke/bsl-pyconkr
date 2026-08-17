from agent_framework.devui import serve

from .config import Settings, seoul_today
from .workflow import create_workflow


def main() -> None:
    settings = Settings()
    workflow = create_workflow(settings=settings, today=seoul_today)
    serve(
        entities=[workflow],
        host="127.0.0.1",
        port=8003,
        auto_open=False,
    )


if __name__ == "__main__":
    main()
