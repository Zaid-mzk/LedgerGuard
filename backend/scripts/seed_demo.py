import secrets
from decimal import Decimal

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.entities import User, Account
from app.core.security import hash_password


db = SessionLocal()

try:
    existing_admin = db.scalar(select(User).where(User.email == "demo.admin@ledgerguard.local"))

    if existing_admin:
        print("Demo users already exist. No changes made. Existing passwords are unchanged.")
    else:
        credentials = [
            ("demo.admin@ledgerguard.local", "admin"),
            ("demo.analyst@ledgerguard.local", "analyst"),
            ("demo.customer@ledgerguard.local", "customer"),
        ]

        users = []

        for email, role in credentials:
            password = secrets.token_urlsafe(18)
            user = User(
                email=email,
                password_hash=hash_password(password),
                role=role,
            )
            db.add(user)
            users.append((user, email, password))

        db.flush()

        admin, analyst, customer = [item[0] for item in users]

        db.add_all(
            [
                Account(
                    owner_user_id=customer.id,
                    account_number="LG1000000001",
                    display_name="Everyday Demo",
                    balance=Decimal("125000.00"),
                ),
                Account(
                    owner_user_id=customer.id,
                    account_number="LG1000000004",
                    display_name="Savings Demo",
                    balance=Decimal("50000.00"),
                ),
                Account(
                    owner_user_id=admin.id,
                    account_number="LG1000000002",
                    display_name="Operations Demo",
                    balance=Decimal("80000.00"),
                ),
                Account(
                    owner_user_id=analyst.id,
                    account_number="LG1000000003",
                    display_name="Analyst Demo",
                    balance=Decimal("50000.00"),
                ),
            ]
        )

        db.commit()

        print("Seeded synthetic demo users and accounts.")
        print("Save these generated local credentials now:")

        for _, email, password in users:
            print(f"{email} | {password}")

        print("Passwords are hashed and are not stored in plaintext.")

except Exception:
    db.rollback()
    raise

finally:
    db.close()
