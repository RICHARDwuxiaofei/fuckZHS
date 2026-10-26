"""Non-blocking profile locks on Windows and Unix."""
import errno
import os


def acquire_profile_lock(path):
    handle = open(path, "a+b")
    try:
        if os.name == "nt":
            import msvcrt
            if os.fstat(handle.fileno()).st_size == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return handle  # Keep open until the process exits or releases the lock.
    except OSError as error:
        handle.close()
        if error.errno in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
            raise BlockingIOError("Another instance is using this profile") from error
        raise
    except BaseException:
        handle.close()
        raise
