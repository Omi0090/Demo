"""Create/remove an isolated account for browser tests. Never use for normal login."""
import json,secrets,sys
from pathlib import Path
from sqlalchemy import select,delete
from pwdlib import PasswordHash
from backend.app.db import Session,User,Audit
path=Path('reports/browser-auth.json')
if '--remove' in sys.argv:
    if path.exists():
        name=json.loads(path.read_text())['username']
        with Session.begin() as s:
            uid=s.scalar(select(User.id).where(User.username==name))
            if uid:
                s.execute(delete(Audit).where(Audit.actor_id==uid));s.execute(delete(User).where(User.id==uid))
        path.unlink()
else:
    credentials={'username':'browser_'+secrets.token_hex(5),'password':secrets.token_urlsafe(24)}
    with Session.begin() as s:s.add(User(username=credentials['username'],password_hash=PasswordHash.recommended().hash(credentials['password']),role='admin'))
    path.parent.mkdir(exist_ok=True);path.write_text(json.dumps(credentials))
    print('Created temporary browser-test account')
