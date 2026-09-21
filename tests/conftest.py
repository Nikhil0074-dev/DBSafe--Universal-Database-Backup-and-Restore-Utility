import sqlite3

import pytest

from app import create_app
from app.services import auth_service

ADMIN_PASSWORD = "Admin@12345"


@pytest.fixture()
def app(tmp_path):
    application = create_app({
        "TESTING": True,
        "ROOT_DIR": tmp_path / "home",
        "SCHEDULER_ENABLED": False,
        "LOG_TO_CONSOLE": False,
        "ADMIN_PASSWORD": ADMIN_PASSWORD,
        "SECRET_KEY": "test-secret-key-for-unit-tests",
        "ENCRYPTION_KEY": "test-encryption-passphrase",
        "MIN_FREE_MB": 0,
    })
    with application.app_context():
        auth_service.reset_login_attempts()
    yield application


class Client:
    """Test client that handles the CSRF token like the browser JS does."""

    def __init__(self, app):
        self.http = app.test_client()
        self.token = self.http.get("/api/auth/csrf").get_json()["csrf_token"]

    def _headers(self):
        return {"X-CSRF-Token": self.token}

    def get(self, url, **kw):
        return self.http.get(url, **kw)

    def post(self, url, json=None, **kw):
        return self.http.post(url, json=json if json is not None else {}, headers=self._headers(), **kw)

    def put(self, url, json=None, **kw):
        return self.http.put(url, json=json or {}, headers=self._headers(), **kw)

    def delete(self, url, **kw):
        return self.http.delete(url, headers=self._headers(), **kw)

    def login(self, username="admin", password=ADMIN_PASSWORD):
        response = self.post("/api/auth/login", {"username": username, "password": password})
        if response.status_code == 200:
            self.token = response.get_json()["csrf_token"]
        return response


@pytest.fixture()
def client(app):
    return Client(app)


@pytest.fixture()
def admin(app):
    c = Client(app)
    assert c.login().status_code == 200
    return c


@pytest.fixture()
def operator(app, admin):
    assert admin.post("/api/users", {"username": "oper", "password": "Operator1", "role": "operator"}).status_code == 201
    c = Client(app)
    assert c.login("oper", "Operator1").status_code == 200
    return c


@pytest.fixture()
def sample_db(tmp_path):
    path = tmp_path / "shop.db"
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
        CREATE TABLE products (id INTEGER PRIMARY KEY, title TEXT, price REAL);
        CREATE INDEX idx_products_title ON products(title);
        CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER, total REAL);
    """)
    conn.executemany("INSERT INTO users (name) VALUES (?)", [(f"user{i}",) for i in range(50)])
    conn.executemany("INSERT INTO products (title, price) VALUES (?, ?)",
                     [(f"item{i}", i * 1.5) for i in range(200)])
    conn.executemany("INSERT INTO orders (user_id, total) VALUES (?, ?)", [(i, i * 2.0) for i in range(30)])
    conn.commit()
    conn.close()
    return path


@pytest.fixture()
def connection(admin, sample_db):
    response = admin.post("/api/databases", {"name": "Shop", "database_type": "sqlite",
                                             "database_name": str(sample_db)})
    assert response.status_code == 201, response.get_json()
    return response.get_json()


def count_rows(path, table):
    conn = sqlite3.connect(path)
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        conn.close()
