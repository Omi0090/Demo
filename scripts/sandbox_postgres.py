"""Sandbox verification helper only. Windows uses normal PostgreSQL installation."""
from pathlib import Path
import signal
import pgserver
server=pgserver.get_server(Path('/home/user/Demo/.pgdata'))
print(server.get_uri(),flush=True)
signal.pause()
