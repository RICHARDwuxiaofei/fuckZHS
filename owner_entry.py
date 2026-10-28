"""Source-only personal desktop app. The sharing entry retains its expiry."""
import sys


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if getattr(sys, "frozen", False):
        raise RuntimeError("Personal entry is for running from source")
    if args[:1] == ["--worker"]:
        from share_worker import main as worker
        return worker(args[1:], owner_mode=True)
    from share_gui import main as gui
    return gui(smoke_test=args == ["--gui-smoke-test"], owner_mode=True)


if __name__ == "__main__":
    raise SystemExit(main())
