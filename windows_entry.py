"""Double-clicking the Windows executable only logs in and fetches courses."""
import sys

if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.argv.extend(["-P", "windows", "-f"])
    import main
