"""Allow `python -m quantsys.cli` execution."""

from .main import main


if __name__ == "__main__":
    raise SystemExit(main())

