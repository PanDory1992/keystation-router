"""Send an allowlisted transport command to the local Studio One MIDI bridge."""
import socket
import sys

if len(sys.argv) != 2:
    raise SystemExit("Usage: python studio_one_command.py ping|play|stop|record|rewind|forward|click")
with socket.create_connection(("127.0.0.1", 47688), timeout=3) as conn:
    conn.sendall((sys.argv[1] + "\n").encode("ascii"))
    print(conn.recv(128).decode("ascii").strip())
