import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_ledgerguard.sqlite3")
os.environ.setdefault("JWT_SECRET", "test-secret-only-not-for-deployment")
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.db.session import Base, get_db
from app.main import app
from app.models.entities import User, Account
from app.core.security import hash_password
from decimal import Decimal


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    app.state.TestingSession = TestingSession
    Base.metadata.create_all(engine)

    def override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    db = TestingSession()
    user = User(email="admin@test.local", password_hash=hash_password("Password!123"), role="admin")
    customer = User(
        email="customer@test.local", password_hash=hash_password("Password!123"), role="customer"
    )
    db.add_all([user, customer])
    db.flush()
    db.add_all(
        [
            Account(
                owner_user_id=customer.id,
                account_number="TEST00000001",
                display_name="Customer",
                balance=Decimal("1000.00"),
            ),
            Account(
                owner_user_id=user.id,
                account_number="TEST00000002",
                display_name="Admin",
                balance=Decimal("500.00"),
            ),
        ]
    )
    db.commit()
    db.close()
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()
