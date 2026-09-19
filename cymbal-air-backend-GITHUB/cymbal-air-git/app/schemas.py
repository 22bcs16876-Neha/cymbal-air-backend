from typing import Optional, List, Any
from pydantic import BaseModel


# ---------- Auth ----------
class PhoneNumberIn(BaseModel):
    phone_number: str


class AuthResult(BaseModel):
    authenticated: Optional[bool] = None
    is_valid: Optional[bool] = None
    error_type: Optional[str] = None


class UserLookupResult(BaseModel):
    user_found: bool
    user_type: Optional[str] = None
    email_ending_in: Optional[str] = None
    phone_ending_in: Optional[str] = None
    message: Optional[str] = None


class CountersOut(BaseModel):
    max_retry_telephone_counter: int = 0
    max_retry_security_ans_count: int = 0
    max_retry_security_key: int = 0
    max_retry_otp_not_received: int = 0
    max_retry_otp_count: int = 0


class RegisterUserIn(BaseModel):
    name: str
    phone_number: str
    email: str


class RegisterUserOut(BaseModel):
    registered: bool
    message: str


class MfaVerifyIn(BaseModel):
    phone_number: str
    security_key: str


class VerifiedOut(BaseModel):
    verified: bool
    reason: Optional[str] = None


class SecurityQuestionIn(BaseModel):
    phone_number: str
    ans: str
    categ: str  # date_of_birth | card_identifier | last_transaction_amount | last_payment_method


class SendOtpIn(BaseModel):
    phone_number: str
    channel: str  # phone | email


class SendOtpOut(BaseModel):
    status: str
    message: str


class VerifyOtpIn(BaseModel):
    phone_number: str
    otp_code: str


class RetryCounterIn(BaseModel):
    current_count: int = 0


class RetryCounterOut(BaseModel):
    new_count: int


class TransferReasonIn(BaseModel):
    phone_number: Optional[str] = None
    reason: str


# ---------- Flights ----------
class SearchFlightsIn(BaseModel):
    origin: str
    destination: str
    departure_date: str
    cabin_class: Optional[str] = "economy"


class FlightOut(BaseModel):
    flight_number: str
    origin: str
    destination: str
    departure_date: Optional[str] = None
    departure_time: str
    arrival_time: str
    cabin_class: Optional[str] = "economy"
    price: float
    currency: str = "USD"
    status: str = "On Time"
    terminal: Optional[str] = None
    gate: Optional[str] = None


class FlightDetailsIn(BaseModel):
    flight_number: str


# ---------- Bookings ----------
class BookingRefIn(BaseModel):
    booking_reference: str


class BookingNameIn(BaseModel):
    booking_name: str
    booking_payment_type: Optional[str] = "booking_pay"


class BookingIdIn(BaseModel):
    booking_id: str


class InitialBookingDataIn(BaseModel):
    phone_number: str


class DuplicateLookupIn(BaseModel):
    last_five_digits: str


class DuplicateDetailsIn(BaseModel):
    duplicate_booking_reference: List[str]


class SendBookingSmsIn(BaseModel):
    booking_id: str
    phone_number: str


class SendFlightDetailsIn(BaseModel):
    channel: str
    flight_number: str
    phone_number: Optional[str] = None
    email: Optional[str] = None


class ReportFlightIssueIn(BaseModel):
    flight_number: str
    issue_description: str
    phone_number: Optional[str] = None


# ---------- Payments / Refunds ----------
class PaymentMethodsIn(BaseModel):
    phone_number: str


class HandleUserInputIn(BaseModel):
    source_last4: str


class ProcessPaymentIn(BaseModel):
    payment_method: str
    amount: float
    source_last4: str
    booking_reference: str
    booking_payment_type: Optional[str] = None


class MobilePaymentLinkIn(BaseModel):
    amount: float
    booking_reference: str
    booking_payment_type: Optional[str] = None
    phone_number: Optional[str] = None


class ProcessRefundIn(BaseModel):
    booking_reference: str
    refund_amount: float
    refund_method: str


class SendRefundInfoIn(BaseModel):
    booking_reference: str
    channel: str
    phone_number: Optional[str] = None
    email: Optional[str] = None


# ---------- Feedback ----------
class FeedbackScoreIn(BaseModel):
    phone_number: Optional[str] = None
    score: Any = None


class FeedbackCommentIn(BaseModel):
    phone_number: Optional[str] = None
    comment_input: Optional[str] = None


# ---------- Stores ----------
class StoreLookupIn(BaseModel):
    zip_code: str


# ---------- Travel Concierge: Hotel ----------
class SearchHotelsIn(BaseModel):
    destination: str
    check_in: str
    check_out: str
    guests: int = 1
    rooms: int = 1
    budget_max: Optional[float] = None
    breakfast_required: bool = False

class HotelDetailsIn(BaseModel):
    hotel_id: str

class CreateHotelReservationIn(BaseModel):
    hotel_id: str
    guest_name: str
    check_in: str
    check_out: str
    guests: int = 1
    rooms: int = 1
    breakfast_required: bool = False

class HotelReservationIn(BaseModel):
    reservation_id: str

class ModifyHotelReservationIn(BaseModel):
    reservation_id: str
    check_in: Optional[str] = None
    check_out: Optional[str] = None
    rooms: Optional[int] = None
    guests: Optional[int] = None

# ---------- Travel Concierge: Ground Transport ----------
class SearchTransportIn(BaseModel):
    city: str
    pickup_location: str
    dropoff_location: str
    pickup_datetime: str
    passengers: int = 1
    vehicle_type: Optional[str] = "private_car"

class TransportDetailsIn(BaseModel):
    transfer_id: str

class CreateTransportReservationIn(BaseModel):
    pickup_location: str
    dropoff_location: str
    pickup_datetime: str
    passengers: int = 1
    vehicle_type: str = "private_car"

class ModifyTransportReservationIn(BaseModel):
    transfer_id: str
    pickup_datetime: Optional[str] = None
    pickup_location: Optional[str] = None
    dropoff_location: Optional[str] = None

# ---------- Travel Concierge: Monitoring / Replanning ----------
class TripContextIn(BaseModel):
    trip_id: Optional[str] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    departure_date: Optional[str] = None
    return_date: Optional[str] = None
    flight_number: Optional[str] = None
    hotel_reservation_id: Optional[str] = None
    transport_reservation_id: Optional[str] = None

class ReplanTripIn(BaseModel):
    trip_id: Optional[str] = None
    reason: str
    origin: Optional[str] = None
    destination: Optional[str] = None
    departure_date: Optional[str] = None
    return_date: Optional[str] = None
    flight_number: Optional[str] = None
    hotel_reservation_id: Optional[str] = None
    transport_reservation_id: Optional[str] = None
    constraints: List[str] = []
