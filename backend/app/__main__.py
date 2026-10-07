import uvicorn
from dotenv import load_dotenv

from . import create_app
from .config import ROOT, Settings


def main():
    load_dotenv(ROOT / ".env", override=False)
    settings = Settings.from_env()
    uvicorn.run(
        create_app(settings),
        host=settings.host,
        port=settings.port,
        reload=False,
        access_log=False,
        log_config=None,
    )


if __name__ == "__main__":
    main()
