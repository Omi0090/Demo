import getpass
import re
from sqlalchemy import select
from pwdlib import PasswordHash
from backend.app.db import Session,User

def main():
    username=input('Admin username: ').strip()
    password=getpass.getpass('Admin password (10+ characters): ')
    if not re.fullmatch(r'[a-zA-Z0-9_.@-]{3,80}',username) or not 10<=len(password)<=128: raise ValueError('Username: 3–80 letters/digits/_.@-; password: 10–128 characters')
    with Session.begin() as s:
        if s.scalar(select(User).where(User.username==username)): raise ValueError('Username already exists')
        s.add(User(username=username,password_hash=PasswordHash.recommended().hash(password),role='admin'))
    print('Administrator created. No default password is stored.')
if __name__=='__main__': main()
