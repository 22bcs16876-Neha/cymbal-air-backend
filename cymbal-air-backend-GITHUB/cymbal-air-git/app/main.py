import datetime as dt
import random
import string
import uuid

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session

from . import models, schemas
from .database import get_db, engine, Base
from .seed import seed as seed_db

app = FastAPI(
    title="Cymbal Air Backend",
    description=(
        "REST backend for the Cymbal Air CX Agent Studio agent. "
        "One POST endpoint per agent Tool, matching the original tool names."
    ),
    version="1.1.0",
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    seed_db()


@app.get("/", tags=["health"])
def health():
    return {
        "status": "ok",
        "service": "cymbal-air-backend",
        "framework": "FastAPI",
        "docs": "/docs",
        "openapi": "/openapi.json",
    }


@app.get("/health", tags=["health"])
def health_alias():
    return {"status": "ok", "service": "cymbal-air-backend"}


@app.get("/healthz", tags=["health"])
def healthz():
    return {"status": "healthy"}


# =========================================================================
# AUTH / IDENTITY
# =========================================================================

@app.post("/tools/authenticate_user", response_model=schemas.AuthResult, tags=["auth"])
def authenticate_user(payload: schemas.PhoneNumberIn, db: Session = Depends(get_db)):
    phone = payload.phone_number.strip()
    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) < 10 or len(digits) > 10:
        return schemas.AuthResult(is_valid=False, error_type="Invalid number")
    user = db.query(models.User).filter(models.User.phone_number == digits).first()
    return schemas.AuthResult(authenticated=user is not None)


@app.post("/tools/get_user_details", response_model=schemas.UserLookupResult, tags=["auth"])
def get_user_details(payload: schemas.PhoneNumberIn, db: Session = Depends(get_db)):
    """Level 0 ANI match — look the caller up by phone number."""
    user = db.query(models.User).filter(models.User.phone_number == payload.phone_number).first()
    if not user:
        return schemas.UserLookupResult(user_found=False, message="No user found with the provided phone number.")
    return schemas.UserLookupResult(
        user_found=True,
        user_type=user.user_type,
        email_ending_in=user.email[0] + "***@" + user.email.split("@")[-1][0] + "*****.com",
        phone_ending_in=user.phone_number[-4:],
    )


@app.post("/tools/create_counters", response_model=schemas.CountersOut, tags=["auth"])
def create_counters(payload: schemas.PhoneNumberIn):
    """Initializes all retry counters to 0 for a new session. Purely stateless —
    the agent stores the returned values as its own session parameters."""
    return schemas.CountersOut()


@app.post("/tools/register_user", response_model=schemas.RegisterUserOut, tags=["auth"])
def register_user(payload: schemas.RegisterUserIn, db: Session = Depends(get_db)):
    phone = payload.phone_number.strip()
    name = payload.name.strip()
    email = payload.email.strip()
    if not phone or not name or not email:
        return schemas.RegisterUserOut(registered=False, message="Name, phone number, and email are required.")

    existing = db.query(models.User).filter(models.User.phone_number == phone).first()
    if existing:
        return schemas.RegisterUserOut(registered=False, message="A passenger is already registered with this phone number.")

    db.add(models.User(phone_number=phone, name=name, email=email, user_type="account_holder"))
    db.commit()
    return schemas.RegisterUserOut(registered=True, message="Passenger registered successfully.")


@app.post("/tools/verify_mfa_code", response_model=schemas.VerifiedOut, tags=["auth"])
def verify_mfa_code(payload: schemas.MfaVerifyIn, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.phone_number == payload.phone_number).first()
    if not user:
        return schemas.VerifiedOut(verified=False, reason="Phone number not found.")
    if user.mfa_key and payload.security_key == user.mfa_key:
        return schemas.VerifiedOut(verified=True)
    return schemas.VerifiedOut(verified=False, reason="The provided security key is invalid.")


@app.post("/tools/verify_security_questions", response_model=schemas.VerifiedOut, tags=["auth"])
def verify_security_questions(payload: schemas.SecurityQuestionIn, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.phone_number == payload.phone_number).first()
    if not user:
        return schemas.VerifiedOut(verified=False, reason="No security questions found for this user.")

    categ = payload.categ
    ans = payload.ans
    ok = False
    if categ == "date_of_birth":
        ok = ans == user.dob
    elif categ == "card_identifier":
        ok = ans == user.card_identifier
    elif categ == "last_transaction_amount":
        try:
            ok = float(ans) == user.last_transaction_amount
        except (TypeError, ValueError):
            ok = False
    elif categ == "last_payment_method":
        ok = ans.lower() == (user.last_payment_method or "").lower()
    else:
        return schemas.VerifiedOut(verified=False, reason=f"Unknown question category '{categ}'.")

    if ok:
        return schemas.VerifiedOut(verified=True)
    return schemas.VerifiedOut(verified=False, reason="The information provided did not match our records.")


def _generate_otp() -> str:
    return "".join(random.choices(string.digits, k=6))


@app.post("/tools/send_otp", response_model=schemas.SendOtpOut, tags=["auth"])
@app.post("/tools/send_one_time_password", response_model=schemas.SendOtpOut, tags=["auth"])
def send_otp(payload: schemas.SendOtpIn, db: Session = Depends(get_db)):
    if payload.channel not in ("phone", "email"):
        return schemas.SendOtpOut(status="FAILURE", message="Invalid channel specified.")
    code = _generate_otp()
    otp = models.Otp(
        phone_number=payload.phone_number, code=code, channel=payload.channel,
        expires_at=dt.datetime.utcnow() + dt.timedelta(minutes=10),
    )
    db.add(otp)
    db.commit()
    # In production: call an SMS/email provider (e.g. Twilio, SendGrid) here instead
    # of returning the code. Returned only so the demo agent can "verify" it end to end.
    return schemas.SendOtpOut(status="SUCCESS", message=f"OTP sent to user's {payload.channel}. (debug code: {code})")


@app.post("/tools/verify_otp", response_model=schemas.VerifiedOut, tags=["auth"])
def verify_otp(payload: schemas.VerifyOtpIn, db: Session = Depends(get_db)):
    otp = (
        db.query(models.Otp)
        .filter(models.Otp.phone_number == payload.phone_number, models.Otp.verified == False)  # noqa: E712
        .order_by(models.Otp.created_at.desc())
        .first()
    )
    if not otp:
        return schemas.VerifiedOut(verified=False, reason="No OTP request found for this number.")
    if otp.expires_at < dt.datetime.utcnow():
        return schemas.VerifiedOut(verified=False, reason="The code has expired. Please request a new one.")
    if otp.code != payload.otp_code:
        return schemas.VerifiedOut(verified=False, reason="The code you entered is incorrect.")
    otp.verified = True
    db.commit()
    return schemas.VerifiedOut(verified=True)


@app.post("/tools/increment_phone_number_retry_count", response_model=schemas.RetryCounterOut, tags=["auth"])
@app.post("/tools/increment_sec_ans_retry_count", response_model=schemas.RetryCounterOut, tags=["auth"])
@app.post("/tools/increment_feedback_retry_count", response_model=schemas.RetryCounterOut, tags=["auth"])
def increment_retry_count(payload: schemas.RetryCounterIn):
    """Stateless increment. CX Agent Studio keeps the counter as a session
    parameter and passes its current value in; the tool just returns +1."""
    return schemas.RetryCounterOut(new_count=payload.current_count + 1)


@app.post("/tools/update_transfer_reason", tags=["auth"])
def update_transfer_reason(payload: schemas.TransferReasonIn, db: Session = Depends(get_db)):
    valid = {"agent", "denial_of_information", "max_no_input", "max_no_match"}
    if payload.reason not in valid:
        raise HTTPException(status_code=400, detail=f"reason must be one of {sorted(valid)}")
    db.add(models.SupportTransfer(phone_number=payload.phone_number, reason=payload.reason))
    db.commit()
    return {"status": "SUCCESS"}


# =========================================================================
# FLIGHTS
# =========================================================================

@app.post("/tools/get_flights", tags=["flights"])
def get_flights(payload: schemas.SearchFlightsIn, db: Session = Depends(get_db)):
    rows = (
        db.query(models.Flight)
        .filter(models.Flight.origin.ilike(payload.origin), models.Flight.destination.ilike(payload.destination))
        .all()
    )
    flights = [
        {
            "flight_number": r.flight_number,
            "origin": payload.origin,
            "destination": payload.destination,
            "departure_date": payload.departure_date,
            "departure_time": r.departure_time,
            "arrival_time": r.arrival_time,
            "cabin_class": payload.cabin_class or "economy",
            "price": r.price,
            "currency": r.currency,
            "status": r.status,
        }
        for r in rows
    ]
    return {"flights": flights, "count": len(flights)}


@app.post("/tools/get_flight_details", tags=["flights"])
def get_flight_details(payload: schemas.FlightDetailsIn, db: Session = Depends(get_db)):
    r = db.query(models.Flight).filter(models.Flight.flight_number == payload.flight_number.upper()).first()
    if not r:
        return {"status": "NOT_FOUND", "flight_number": payload.flight_number}
    return {
        "flight_number": r.flight_number, "origin": r.origin, "destination": r.destination,
        "departure_time": r.departure_time, "arrival_time": r.arrival_time,
        "terminal": r.terminal, "gate": r.gate, "status": r.status,
    }


@app.post("/tools/send_flight_details", tags=["flights"])
def send_flight_details(payload: schemas.SendFlightDetailsIn):
    if payload.channel.lower() not in ("email", "mobile"):
        return {"status": "FAILED", "message": "Invalid channel specified."}
    # In production: send via email/SMS provider here.
    return {"status": "SUCCESS", "message": f"Details for flight {payload.flight_number} have been sent to your registered {payload.channel}."}


@app.post("/tools/report_flight_issue", tags=["flights"])
def report_flight_issue(payload: schemas.ReportFlightIssueIn, db: Session = Depends(get_db)):
    ticket_id = f"AIR-TICKET-{uuid.uuid4().hex[:8].upper()}"
    db.add(models.FlightIssueReport(
        ticket_id=ticket_id, phone_number=payload.phone_number,
        flight_number=payload.flight_number, issue_description=payload.issue_description,
    ))
    db.commit()
    return {"status": "SUCCESS", "ticket_id": ticket_id, "flight_number": payload.flight_number}


# =========================================================================
# BOOKINGS
# =========================================================================

def _booking_to_dict(b: models.Booking) -> dict:
    return {
        "booking_found": True,
        "booking_reference": b.booking_reference,
        "flight": b.flight_number,
        "origin": b.origin,
        "destination": b.destination,
        "departure_date": b.departure_date,
        "booking_status": b.booking_status,
        "original_payment_method": b.original_payment_method,
        "refund_eligible": b.refund_eligible,
        "refund_amount": b.refund_amount,
        "currency": b.currency,
        "refund_fee": b.refund_fee,
    }


@app.post("/tools/verify_booking", tags=["bookings"])
def verify_booking(payload: schemas.BookingRefIn, db: Session = Depends(get_db)):
    ref = payload.booking_reference.strip().upper()
    b = db.query(models.Booking).filter(models.Booking.booking_reference == ref).first()
    if not b:
        return {"booking_found": False, "error": "Booking not found."}
    return {"booking_found": True, "booking_reference": ref, "amount_due": b.amount_due,
            "currency": b.currency, "booking_status": b.booking_status}


@app.post("/tools/get_booking_amount", tags=["bookings"])
def get_booking_amount(payload: schemas.BookingRefIn, db: Session = Depends(get_db)):
    ref = payload.booking_reference.strip().upper()
    b = db.query(models.Booking).filter(models.Booking.booking_reference == ref).first()
    if not b:
        return {"booking_found": False, "error": "Booking reference not found. Please check the reference and try again."}
    return {"booking_found": True, "booking_reference": ref, "amount_due": b.amount_due,
            "currency": b.currency, "booking_status": b.booking_status}


@app.post("/tools/get_booking_details", tags=["bookings"])
def get_booking_details(payload: schemas.BookingRefIn, db: Session = Depends(get_db)):
    ref = payload.booking_reference.strip().upper()
    b = db.query(models.Booking).filter(models.Booking.booking_reference == ref).first()
    if not b:
        return {"booking_found": False, "error": "Booking not found. Please check the booking reference and try again."}
    return _booking_to_dict(b)


@app.post("/tools/get_booking_status", tags=["bookings"])
def get_booking_status(payload: schemas.BookingIdIn, db: Session = Depends(get_db)):
    b = db.query(models.Booking).filter(models.Booking.booking_reference == payload.booking_id).first()
    if not b:
        return {"error": "Not Found", "message": f"No booking found with reference {payload.booking_id}."}
    return _booking_to_dict(b)


@app.post("/tools/verify_booking_name", tags=["bookings"])
def verify_booking_name(payload: schemas.BookingNameIn, db: Session = Depends(get_db)):
    name = payload.booking_name.strip().lower()
    b = db.query(models.Booking).filter(models.Booking.booking_name == name).first()
    if not b:
        return {"error": "Booking name not found."}
    return {"account_number_last4": b.account_number_last4}


@app.post("/tools/get_initial_booking_data", tags=["bookings"])
def get_initial_booking_data(payload: schemas.InitialBookingDataIn, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.phone_number == payload.phone_number).first()
    booking = (
        db.query(models.Booking)
        .filter(models.Booking.user_phone == payload.phone_number)
        .order_by(models.Booking.booking_date.desc())
        .first()
    )
    return {
        "user_first_name": user.name.split(" ")[0] if user else None,
        "most_recent_booking_id": booking.booking_reference if booking else None,
    }


@app.post("/tools/find_duplicate_bookings", tags=["bookings"])
def find_duplicate_bookings(payload: schemas.DuplicateLookupIn, db: Session = Depends(get_db)):
    rows = db.query(models.Booking).filter(models.Booking.booking_reference.like(f"%{payload.last_five_digits}")).all()
    return {
        "all_booking_id": [r.booking_reference for r in rows],
        "all_booking_date": [r.booking_date or "N/A" for r in rows],
        "all_booking_time": [r.booking_time or "N/A" for r in rows],
    }


@app.post("/tools/get_duplicate_booking_details", tags=["bookings"])
def get_duplicate_booking_details(payload: schemas.DuplicateDetailsIn, db: Session = Depends(get_db)):
    out = []
    for ref in payload.duplicate_booking_reference:
        b = db.query(models.Booking).filter(models.Booking.booking_reference == ref).first()
        if b:
            out.append({"booking_reference": ref, "flight_date": b.departure_date, "flight_time": b.booking_time})
        else:
            out.append({"booking_reference": ref, "flight_date": None, "flight_time": None})
    return {"bookings": out}


@app.post("/tools/send_booking_status_sms", tags=["bookings"])
def send_booking_status_sms(payload: schemas.SendBookingSmsIn):
    if not payload.phone_number:
        return {"status": "ERROR", "message": "Could not find a registered phone number in the session."}
    # In production: call an SMS provider here.
    return {"status": "SUCCESS", "message": f"Booking status sent to registered phone number for {payload.booking_id}"}


# =========================================================================
# PAYMENTS / REFUNDS
# =========================================================================

@app.post("/tools/get_user_payment_methods", tags=["payments"])
def get_user_payment_methods(payload: schemas.PaymentMethodsIn, db: Session = Depends(get_db)):
    rows = db.query(models.PaymentMethod).filter(models.PaymentMethod.user_phone == payload.phone_number).all()
    return {
        "bank_accounts": [
            {"source_last4": r.source_last4, "booking_payment_type": r.label}
            for r in rows if r.method_type == "bank_account"
        ],
        "debit_cards": [
            {"source_last4": r.source_last4} for r in rows if r.method_type == "debit_card"
        ],
        "credit_cards": [
            {"source_last4": r.source_last4} for r in rows if r.method_type == "credit_card"
        ],
    }


@app.post("/tools/handle_user_input", tags=["payments"])
def handle_user_input(payload: schemas.HandleUserInputIn):
    valid = len(payload.source_last4) == 4 and payload.source_last4.isdigit()
    return {"valid": valid}


@app.post("/tools/process_payment", tags=["payments"])
def process_payment(payload: schemas.ProcessPaymentIn, db: Session = Depends(get_db)):
    status_code = "SUCCESS"
    message = f"Payment of {payload.amount:.2f} for airline booking {payload.booking_reference} was successful."
    payment_ref = f"PAY-{payload.booking_reference}-{uuid.uuid4().hex[:6].upper()}"

    if payload.source_last4 == "1002":
        status_code, message = "INSUFFICIENT_FUNDS", "Your payment failed due to insufficient funds in the selected account."
    elif payload.source_last4 == "2345" and payload.payment_method == "debit_card" and payload.amount > 1000:
        status_code, message = "LIMIT_EXCEEDED", "Your payment failed because the debit card transaction limit was exceeded."

    db.add(models.Payment(
        payment_reference=payment_ref, booking_reference=payload.booking_reference,
        amount=payload.amount, payment_method=payload.payment_method,
        source_last4=payload.source_last4, status_code=status_code,
    ))
    if status_code == "SUCCESS":
        booking = db.query(models.Booking).filter(models.Booking.booking_reference == payload.booking_reference).first()
        if booking:
            booking.booking_status = "CONFIRMED"
    db.commit()

    result = {"payment_status_code": status_code, "message": message}
    if status_code == "SUCCESS":
        result["payment_reference"] = payment_ref
    return result


@app.post("/tools/send_mobile_payment_link", tags=["payments"])
def send_mobile_payment_link(payload: schemas.MobilePaymentLinkIn):
    return {
        "link_sent": True,
        "message": f"A payment link for {payload.amount:.2f} for booking {payload.booking_reference} was sent to the registered mobile number.",
    }


@app.post("/tools/process_refund", tags=["payments"])
def process_refund(payload: schemas.ProcessRefundIn, db: Session = Depends(get_db)):
    if not payload.booking_reference or payload.refund_amount <= 0 or not payload.refund_method:
        return {"success": False, "error": "Incomplete refund information."}
    ref = payload.booking_reference.strip().upper()
    refund_ref = f"REF-{ref}-{uuid.uuid4().hex[:6].upper()}"
    db.add(models.Refund(
        refund_reference=refund_ref, booking_reference=ref,
        amount=payload.refund_amount, method=payload.refund_method,
    ))
    db.commit()
    return {
        "success": True,
        "refund_status": "INITIATED",
        "refund_reference": refund_ref,
        "message": f"Refund of {payload.refund_amount:.2f} for booking {ref} has been initiated to {payload.refund_method}.",
    }


@app.post("/tools/send_refund_information", tags=["payments"])
def send_refund_information(payload: schemas.SendRefundInfoIn):
    return {"status": "SUCCESS", "message": f"Refund instructions for booking {payload.booking_reference} were sent to the registered {payload.channel}."}


# =========================================================================
# FEEDBACK
# =========================================================================

@app.post("/tools/update_feedback_score", tags=["feedback"])
def update_feedback_score(payload: schemas.FeedbackScoreIn, db: Session = Depends(get_db)):
    valid_scores = {1, 2, 3, 4, 5}
    if payload.score is None:
        return {"message": "Input score is None. Feedback score not set."}
    try:
        score = int(payload.score)
    except (ValueError, TypeError):
        return {"message": f"Input '{payload.score}' is not a valid integer."}
    if score not in valid_scores:
        return {"message": f"Input '{score}' is not one of the valid scores (1, 2, 3, 4, 5). Feedback score not set."}

    fb = models.Feedback(phone_number=payload.phone_number, score=score)
    db.add(fb)
    db.commit()
    return {"message": f"feedback_score variable is updated successfully with {score}", "feedback_id": fb.id}


@app.post("/tools/update_feedback_comment", tags=["feedback"])
def update_feedback_comment(payload: schemas.FeedbackCommentIn, db: Session = Depends(get_db)):
    comment_input = payload.comment_input
    if comment_input is None:
        return {"message": "No Feedback comment provided"}
    if not isinstance(comment_input, str):
        return {"message": f"Invalid input type for comment: {type(comment_input).__name__}. Expected string. Storing empty comment."}
    comment = comment_input.strip()
    if not comment:
        return {"message": "Feedback comment is empty after stripping whitespace. Storing empty comment."}

    # attach to the most recent feedback row for this phone number if one exists, else create one
    fb = None
    if payload.phone_number:
        fb = (
            db.query(models.Feedback)
            .filter(models.Feedback.phone_number == payload.phone_number)
            .order_by(models.Feedback.created_at.desc())
            .first()
        )
    if not fb:
        fb = models.Feedback(phone_number=payload.phone_number)
        db.add(fb)
    fb.comment = comment
    db.commit()
    return {"message": "feedback_comment variable has been populated successfully."}


# =========================================================================
# STORES
# =========================================================================

@app.post("/tools/get_store_details", tags=["stores"])
def get_store_details(payload: schemas.StoreLookupIn, db: Session = Depends(get_db)):
    rows = db.query(models.Store).filter(models.Store.zip_code == payload.zip_code.strip()).all()
    return {"stores": [{"id": r.id, "address": r.address} for r in rows]}


# =========================================================================
# TRAVEL CONCIERGE — HOTEL
# =========================================================================

_DEMO_HOTELS = [
    {"hotel_id":"CIT-LON","name":"citizenM Tower of London","city":"London","area":"Tower Hill",
     "nightly_rate":260.0,"currency":"USD","breakfast_included":True,"rating":4.5,
     "cancellation":"Free cancellation up to 24 hours before check-in"},
    {"hotel_id":"HIL-LON","name":"Hilton London Bankside","city":"London","area":"Bankside",
     "nightly_rate":315.0,"currency":"USD","breakfast_included":False,"rating":4.6,
     "cancellation":"Free cancellation up to 48 hours before check-in"},
    {"hotel_id":"PRE-LON","name":"Premier Inn London County Hall","city":"London","area":"South Bank",
     "nightly_rate":190.0,"currency":"USD","breakfast_included":False,"rating":4.3,
     "cancellation":"Free cancellation up to 24 hours before check-in"},
]

@app.post("/tools/search_hotels", tags=["hotels"])
def search_hotels(payload: schemas.SearchHotelsIn):
    hotels = [h.copy() for h in _DEMO_HOTELS if h["city"].lower() == payload.destination.strip().lower()]
    if payload.budget_max is not None:
        hotels = [h for h in hotels if h["nightly_rate"] <= payload.budget_max]
    if payload.breakfast_required:
        hotels = [h for h in hotels if h["breakfast_included"]]
    for h in hotels:
        h["total_estimated"] = h["nightly_rate"] * max(1, _nights(payload.check_in, payload.check_out)) * payload.rooms
    return {"status":"SUCCESS","demo":True,"hotels":hotels,"count":len(hotels)}

@app.post("/tools/get_hotel_details", tags=["hotels"])
def get_hotel_details(payload: schemas.HotelDetailsIn):
    h = next((x for x in _DEMO_HOTELS if x["hotel_id"].upper() == payload.hotel_id.upper()), None)
    return {"status":"SUCCESS","demo":True,"hotel":h} if h else {"status":"NOT_FOUND","hotel_id":payload.hotel_id}

@app.post("/tools/create_hotel_reservation", tags=["hotels"])
def create_hotel_reservation(payload: schemas.CreateHotelReservationIn):
    ref = f"{payload.hotel_id.upper()}-{uuid.uuid4().hex[:6].upper()}"
    nights = _nights(payload.check_in, payload.check_out)
    hotel = next((x for x in _DEMO_HOTELS if x["hotel_id"].upper()==payload.hotel_id.upper()), None)
    rate = hotel["nightly_rate"] if hotel else 200.0
    total = rate * nights * payload.rooms
    return {"status":"CONFIRMED_DEMO","demo":True,"reservation_id":ref,
            "hotel_id":payload.hotel_id,"guest_name":payload.guest_name,
            "check_in":payload.check_in,"check_out":payload.check_out,
            "nights":nights,"total":total,"currency":"USD"}

@app.post("/tools/get_hotel_reservation", tags=["hotels"])
def get_hotel_reservation(payload: schemas.HotelReservationIn):
    return {"status":"CONFIRMED_DEMO","demo":True,"reservation_id":payload.reservation_id,
            "message":"Demo hotel reservation is active."}

@app.post("/tools/modify_hotel_reservation", tags=["hotels"])
def modify_hotel_reservation(payload: schemas.ModifyHotelReservationIn):
    return {"status":"MODIFICATION_PROPOSED_DEMO","demo":True,"reservation_id":payload.reservation_id,
            "check_in":payload.check_in,"check_out":payload.check_out,
            "rooms":payload.rooms,"guests":payload.guests,
            "requires_user_consent":True}

@app.post("/tools/cancel_hotel_reservation", tags=["hotels"])
def cancel_hotel_reservation(payload: schemas.HotelReservationIn):
    return {"status":"CANCELLED_DEMO","demo":True,"reservation_id":payload.reservation_id}

# =========================================================================
# TRAVEL CONCIERGE — TRANSPORT
# =========================================================================

_DEMO_TRANSPORT = [
    {"vehicle_type":"private_car","provider":"Cymbal Executive Cars","price":95.0,"currency":"USD","capacity":3},
    {"vehicle_type":"premium_van","provider":"Cymbal Executive Vans","price":145.0,"currency":"USD","capacity":6},
    {"vehicle_type":"airport_shuttle","provider":"Cymbal Airport Shuttle","price":45.0,"currency":"USD","capacity":8},
]

@app.post("/tools/search_transport", tags=["transport"])
def search_transport(payload: schemas.SearchTransportIn):
    options=[x for x in _DEMO_TRANSPORT if x["capacity"] >= payload.passengers]
    if payload.vehicle_type:
        requested=payload.vehicle_type.lower()
        exact=[x for x in options if x["vehicle_type"].lower()==requested]
        if exact: options=exact
    return {"status":"SUCCESS","demo":True,"options":options,"count":len(options)}

@app.post("/tools/get_transport_details", tags=["transport"])
def get_transport_details(payload: schemas.TransportDetailsIn):
    return {"status":"CONFIRMED_DEMO","demo":True,"transfer_id":payload.transfer_id,
            "message":"Demo transport reservation is active."}

@app.post("/tools/create_transport_reservation", tags=["transport"])
def create_transport_reservation(payload: schemas.CreateTransportReservationIn):
    ref=f"TRANS-{uuid.uuid4().hex[:8].upper()}"
    vehicle=next((x for x in _DEMO_TRANSPORT if x["vehicle_type"]==payload.vehicle_type), _DEMO_TRANSPORT[0])
    return {"status":"CONFIRMED_DEMO","demo":True,"transfer_id":ref,
            "pickup_location":payload.pickup_location,"dropoff_location":payload.dropoff_location,
            "pickup_datetime":payload.pickup_datetime,"passengers":payload.passengers,
            "vehicle_type":vehicle["vehicle_type"],"provider":vehicle["provider"],
            "total":vehicle["price"],"currency":vehicle["currency"]}

@app.post("/tools/modify_transport_reservation", tags=["transport"])
def modify_transport_reservation(payload: schemas.ModifyTransportReservationIn):
    return {"status":"MODIFICATION_PROPOSED_DEMO","demo":True,"transfer_id":payload.transfer_id,
            "pickup_datetime":payload.pickup_datetime,"pickup_location":payload.pickup_location,
            "dropoff_location":payload.dropoff_location,"requires_user_consent":True}

@app.post("/tools/cancel_transport_reservation", tags=["transport"])
def cancel_transport_reservation(payload: schemas.TransportDetailsIn):
    return {"status":"CANCELLED_DEMO","demo":True,"transfer_id":payload.transfer_id}

# =========================================================================
# TRAVEL CONCIERGE — TRIP MONITOR / REPLANNING
# =========================================================================

@app.post("/tools/get_trip_status", tags=["trip_monitor"])
def get_trip_status(payload: schemas.TripContextIn):
    return {"status":"ACTIVE_DEMO","demo":True,"trip_id":payload.trip_id,
            "flight_number":payload.flight_number,
            "hotel_reservation_id":payload.hotel_reservation_id,
            "transport_reservation_id":payload.transport_reservation_id,
            "material_changes":[]}

@app.post("/tools/check_trip_disruptions", tags=["trip_monitor"])
def check_trip_disruptions(payload: schemas.TripContextIn):
    return {"status":"NO_MATERIAL_DISRUPTIONS_DEMO","demo":True,
            "trip_id":payload.trip_id,"events":[],"monitoring_source":"demo backend"}

@app.post("/tools/replan_trip", tags=["replanning"])
def replan_trip(payload: schemas.ReplanTripIn):
    return {"status":"REPLAN_PROPOSED_DEMO","demo":True,
            "trip_id":payload.trip_id,"reason":payload.reason,
            "current_state":{"flight_number":payload.flight_number,
                             "hotel_reservation_id":payload.hotel_reservation_id,
                             "transport_reservation_id":payload.transport_reservation_id},
            "alternatives":[
                {"option":"Preserve confirmed bookings and adjust dependent timing",
                 "requires_user_consent":True},
                {"option":"Search replacement flight/hotel/transport based on updated constraints",
                 "requires_user_consent":True}
            ]}

def _nights(check_in: str, check_out: str) -> int:
    try:
        a=dt.date.fromisoformat(check_in); b=dt.date.fromisoformat(check_out)
        return max(1,(b-a).days)
    except Exception:
        return 1
