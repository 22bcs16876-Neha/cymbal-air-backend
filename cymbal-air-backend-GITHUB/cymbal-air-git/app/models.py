import datetime as dt
from sqlalchemy import (
    Column, String, Float, Integer, Boolean, DateTime, ForeignKey
)
from sqlalchemy.orm import relationship
from .database import Base


class User(Base):
    __tablename__ = "users"

    phone_number = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    user_type = Column(String, default="account_holder")  # account_holder | card_holder
    mfa_key = Column(String, nullable=True)  # 6-digit TOTP-style key for Level-2 auth

    # security-question answers (Level-1 auth)
    dob = Column(String, nullable=True)
    card_identifier = Column(String, nullable=True)
    last_transaction_amount = Column(Float, nullable=True)
    last_payment_method = Column(String, nullable=True)

    payment_methods = relationship("PaymentMethod", back_populates="user")
    bookings = relationship("Booking", back_populates="user")


class PaymentMethod(Base):
    __tablename__ = "payment_methods"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_phone = Column(String, ForeignKey("users.phone_number"), index=True)
    method_type = Column(String)  # bank_account | debit_card | credit_card
    label = Column(String, nullable=True)  # e.g. Savings / Checking
    source_last4 = Column(String)

    user = relationship("User", back_populates="payment_methods")


class Flight(Base):
    __tablename__ = "flights"

    flight_number = Column(String, primary_key=True, index=True)
    origin = Column(String, index=True)
    destination = Column(String, index=True)
    departure_date = Column(String, nullable=True)  # YYYY-MM-DD, null = template/recurring
    departure_time = Column(String)
    arrival_time = Column(String)
    terminal = Column(String, nullable=True)
    gate = Column(String, nullable=True)
    cabin_class = Column(String, default="economy")
    price = Column(Float, default=0.0)
    currency = Column(String, default="USD")
    status = Column(String, default="On Time")


class Booking(Base):
    __tablename__ = "bookings"

    booking_reference = Column(String, primary_key=True, index=True)
    user_phone = Column(String, ForeignKey("users.phone_number"), nullable=True)
    booking_name = Column(String, nullable=True, index=True)  # name booking was made under
    flight_number = Column(String, nullable=True)
    origin = Column(String, nullable=True)
    destination = Column(String, nullable=True)
    departure_date = Column(String, nullable=True)
    booking_date = Column(String, nullable=True)
    booking_time = Column(String, nullable=True)
    booking_status = Column(String, default="CONFIRMED")  # CONFIRMED | CANCELLED
    amount_due = Column(Float, default=0.0)
    currency = Column(String, default="USD")
    original_payment_method = Column(String, nullable=True)
    account_number_last4 = Column(String, nullable=True)
    refund_eligible = Column(Boolean, default=True)
    refund_amount = Column(Float, nullable=True)
    refund_fee = Column(Float, default=0.0)

    user = relationship("User", back_populates="bookings")


class Payment(Base):
    __tablename__ = "payments"

    payment_reference = Column(String, primary_key=True, index=True)
    booking_reference = Column(String, ForeignKey("bookings.booking_reference"))
    amount = Column(Float)
    payment_method = Column(String)
    source_last4 = Column(String, nullable=True)
    status_code = Column(String)  # SUCCESS | INSUFFICIENT_FUNDS | LIMIT_EXCEEDED
    created_at = Column(DateTime, default=dt.datetime.utcnow)


class Refund(Base):
    __tablename__ = "refunds"

    refund_reference = Column(String, primary_key=True, index=True)
    booking_reference = Column(String, ForeignKey("bookings.booking_reference"))
    amount = Column(Float)
    method = Column(String)
    status = Column(String, default="INITIATED")
    created_at = Column(DateTime, default=dt.datetime.utcnow)


class Otp(Base):
    __tablename__ = "otps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    phone_number = Column(String, index=True)
    code = Column(String)
    channel = Column(String)
    verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    expires_at = Column(DateTime)


class Store(Base):
    __tablename__ = "stores"

    id = Column(String, primary_key=True)
    zip_code = Column(String, index=True)
    address = Column(String)


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    phone_number = Column(String, nullable=True)
    score = Column(Integer, nullable=True)
    comment = Column(String, nullable=True)
    created_at = Column(DateTime, default=dt.datetime.utcnow)


class SupportTransfer(Base):
    """Audit log of conversations handed off / exited early (transfer_reason)."""
    __tablename__ = "support_transfers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    phone_number = Column(String, nullable=True)
    reason = Column(String)  # agent | denial_of_information | max_no_input | max_no_match
    created_at = Column(DateTime, default=dt.datetime.utcnow)


class FlightIssueReport(Base):
    __tablename__ = "flight_issue_reports"

    ticket_id = Column(String, primary_key=True)
    phone_number = Column(String, nullable=True)
    flight_number = Column(String)
    issue_description = Column(String)
    status = Column(String, default="SUCCESS")
    created_at = Column(DateTime, default=dt.datetime.utcnow)
