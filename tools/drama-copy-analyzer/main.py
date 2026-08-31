import sys


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        from self_check import run_checks

        run_checks(include_docs=False, verbose=False)
        raise SystemExit(0)

    from gui import start_app

    start_app()
