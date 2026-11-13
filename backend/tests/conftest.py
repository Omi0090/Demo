def pytest_addoption(parser):
    parser.addoption('--run-integration',action='store_true',default=False,help='Exercise actual local PostgreSQL integration')
