"""Interactive local configuration: secrets never appear in terminal output."""
import getpass
import secrets
from pathlib import Path
from urllib.parse import quote

def main():
    path=Path('.env')
    if path.exists() and input('.env exists. Replace it? [y/N] ').lower()!='y':return
    host=input('PostgreSQL host [localhost]: ').strip() or 'localhost'
    port=int(input('PostgreSQL port [5432]: ').strip() or '5432')
    database=input('Database [healthcare_fraud]: ').strip() or 'healthcare_fraud'
    username=input('Database user [healthcare]: ').strip() or 'healthcare'
    password=getpass.getpass('Database password: ')
    url=f'postgresql+psycopg://{quote(username,safe="")}:{quote(password,safe="")}@{host}:{port}/{quote(database,safe="")}'
    path.write_text(f'DATABASE_URL={url}\nJWT_SECRET={secrets.token_urlsafe(48)}\nJWT_EXPIRE_MINUTES=60\nFRONTEND_ORIGIN=http://localhost:5173\n',encoding='utf-8')
    print('Saved local .env with a generated JWT secret. Keep this file private.')
if __name__=='__main__':main()
