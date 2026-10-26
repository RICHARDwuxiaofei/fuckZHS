"""The sharing GUI has its own silent expiry; main.py remains the owner's CLI."""
import sys
from share_policy import access_allowed


def main(argv=None):
    if not access_allowed():
        return 0
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["--worker"]:
        from share_worker import main as worker
        return worker(argv[1:])
    if argv == ["--gui-smoke-test"]:
        from share_gui import main as gui
        return gui(smoke_test=True)
    if argv in (["-h"], ["--help"]):
        return 0
    from share_gui import main as gui
    return gui()


if __name__ == "__main__":
    raise SystemExit(main())
