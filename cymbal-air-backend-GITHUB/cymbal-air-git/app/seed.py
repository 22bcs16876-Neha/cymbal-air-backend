"""
Seeds the database with data equivalent to the hardcoded mock dictionaries
found in the original CX Agent Studio python_function tools, so the agent's
behavior is unchanged after switching to real REST tools.

Run once: `python -m app.seed`  (also auto-run on container startup if DB is empty)
"""
from .database import SessionLocal, engine, Base
from . import models


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(models.User).count() > 0:
            print("Database already seeded, skipping.")
            return

        # --- Users (Level 0 ANI match + Level 1 security Qs + Level 2 MFA key) ---
        users = [
            models.User(
                phone_number="16502530000", name="Alex Rivera", email="alex.rivera@example.com",
                user_type="account_holder", mfa_key="232425",
                dob="1995-02-03", card_identifier="1234",
                last_transaction_amount=500.00, last_payment_method="online",
            ),
            models.User(
                phone_number="15551234567", name="Jamie Chen", email="jamie.chen@example.com",
                user_type="card_holder", mfa_key=None,
                dob="1988-10-20", card_identifier="7890",
                last_transaction_amount=150.75, last_payment_method="debit",
            ),
        ]
        db.add_all(users)

        # --- Payment methods for the primary demo user ---
        db.add_all([
            models.PaymentMethod(user_phone="16502530000", method_type="bank_account",
                                  label="Savings", source_last4="1001"),
            models.PaymentMethod(user_phone="16502530000", method_type="bank_account",
                                  label="Checking", source_last4="1002"),
            models.PaymentMethod(user_phone="16502530000", method_type="debit_card",
                                  label=None, source_last4="2345"),
        ])

        # --- Flights (a small static route network, easy to extend) ---
        flights = [
            models.Flight(flight_number="CA101", origin="Delhi", destination="London",
                          departure_time="09:00", arrival_time="13:30", terminal="3", gate="A12",
                          price=420, status="On Time"),
            models.Flight(flight_number="CA102", origin="Delhi", destination="London",
                          departure_time="14:30", arrival_time="19:10", terminal="3", gate="A18",
                          price=365, status="Delayed"),
            models.Flight(flight_number="CA103", origin="Delhi", destination="London",
                          departure_time="20:00", arrival_time="00:40 +1 day", terminal="3", gate="A22",
                          price=390, status="On Time"),
            models.Flight(flight_number="AI102", origin="Delhi", destination="London",
                          departure_time="10:00", arrival_time="14:30", terminal="2", gate="B4",
                          price=300, status="On Time"),
            models.Flight(flight_number="3W817", origin="New York", destination="Budapest",
                          departure_time="18:00", arrival_time="08:15 +1 day", terminal="4", gate="C7",
                          price=254, status="On Time"),
            models.Flight(flight_number="AI1020", origin="Mumbai", destination="Singapore",
                          departure_time="23:00", arrival_time="07:30 +1 day", terminal="2", gate="D1",
                          price=180, status="Cancelled"),
        ]
        db.add_all(flights)

        # --- Bookings ---
        bookings = [
            models.Booking(
                booking_reference="ABC123", user_phone="16502530000", booking_name="jane",
                flight_number="AI102", origin="Delhi", destination="London",
                departure_date="2026-10-10", booking_date="2026-09-01", booking_time="14:00",
                booking_status="CONFIRMED", amount_due=300.0, currency="USD",
                original_payment_method="credit_card", account_number_last4="7821",
                refund_eligible=True, refund_amount=300.0, refund_fee=0.0,
            ),
            models.Booking(
                booking_reference="3W817T", user_phone="15551234567", booking_name="jamie",
                flight_number="3W817", origin="New York", destination="Budapest",
                departure_date="2026-12-01", booking_date="2026-09-02", booking_time="14:01",
                booking_status="CONFIRMED", amount_due=254.0, currency="USD",
                original_payment_method="credit_card",
                refund_eligible=True, refund_amount=254.0, refund_fee=0.0,
            ),
            models.Booking(
                booking_reference="AI1020", user_phone=None, booking_name=None,
                flight_number="AI1020", origin="Mumbai", destination="Singapore",
                departure_date="2026-10-15", booking_date="2026-09-03", booking_time="14:02",
                booking_status="CANCELLED", amount_due=180.0, currency="USD",
                original_payment_method="debit_card",
                refund_eligible=True, refund_amount=180.0, refund_fee=0.0,
            ),
            # extra bookings sharing last-5-digits "12355" for the find_duplicate_bookings demo
            models.Booking(
                booking_reference="ABC12355", user_phone="16502530000", booking_status="CONFIRMED",
                flight_number="CA101", origin="Delhi", destination="London",
                departure_date="2026-11-05", booking_date="2026-09-04", booking_time="09:00",
                amount_due=420.0,
            ),
            models.Booking(
                booking_reference="LLM12355", user_phone="16502530000", booking_status="CONFIRMED",
                flight_number="CA102", origin="Delhi", destination="London",
                departure_date="2026-11-06", booking_date="2026-09-05", booking_time="10:00",
                amount_due=365.0,
            ),
        ]
        db.add_all(bookings)

        # --- Stores ---
        db.add_all([
            models.Store(id="STORE-AUS-01", zip_code="78701",
                         address="Google Texas, 500 W 2nd St, Suite 2900 Austin, Texas 78701, US"),
            models.Store(id="STORE-CA-02", zip_code="78701",
                         address="Google California, 19510 Jamboree Road, Irvine, California 92612, US"),
        ])

        db.commit()
        print("Database seeded successfully.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
