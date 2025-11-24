import logging
from sqlalchemy.exc import SQLAlchemyError
from flask import Blueprint, request, jsonify, current_app
from app import db, limiter
from app.models import User, Discount, Claimed
from app.constants import (
    RATE_LIMIT_STANDARD,
    RATE_LIMIT_AUTOCOMPLETE,
    RATE_LIMIT_AUTOCOMPLETE_DAILY,
    RATE_LIMIT_PLACE_DETAILS,
    HTTP_400_BAD_REQUEST,
    HTTP_500_INTERNAL_SERVER_ERROR
)
from .validators import AutocompleteInput, PlaceDetailsInput, InitialLoadInput, GetRerollDiscountInput, ClaimDiscountInput
from datetime import datetime, timezone
from app.helpers import (
    get_random_discount,
    render_voucher,
    render_home,
    get_user_state,
    render_claimed_voucher,
    render_redeemed,
    return_generic_error,
    get_stores_with_discounts,
)
import requests
import sentry_sdk

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

api = Blueprint("api", __name__)


@api.route("/initial_load", methods=["POST"])
def initial_load():
    """Handle initial load of the application."""
    try:
        inputs = InitialLoadInput(request)
        
        if not inputs.validate():
            sentry_sdk.capture_message(inputs.errors, level="warning")
            return jsonify({"error": "Invalid input", "messages": inputs.errors}), HTTP_400_BAD_REQUEST
        
        data = request.get_json()

             
        device_id = data.get("device_id")
        user_timezone = data.get("timezone")

   

        if not data or not device_id or not user_timezone:
            logger.warning("Missing required data in initial_load request")
            return return_generic_error()

        user = User.query.filter_by(device_id=device_id).first()

        if user:
            state, discount, claimed = get_user_state(user.id)

            if state == "home":
                categories = (
                    db.session.query(Discount.category)
                    .filter(Discount.available == True)
                    .distinct()
                    .all()
                )
                categories = ["Any"] + [category[0] for category in categories]

                return render_home(categories)
            elif state == "reroll":
                return render_voucher(discount, user, claimed.selected_category)
            elif state == "voucher":
                return render_claimed_voucher(discount, claimed)
            elif state == "redeemed":
                return render_redeemed()

            logger.error(f"Unexpected state in initial_load: {state}")
        else:
            categories = (
                    db.session.query(Discount.category)
                    .filter(Discount.available == True)
                    .distinct()
                    .all()
                )
            categories = ["Any"] + [category[0] for category in categories]
            return render_home(categories)
        
        return jsonify({"error": "An unexpected error occurred"}), HTTP_500_INTERNAL_SERVER_ERROR
    except Exception as e:
        logger.error(f"Error in initial_load: {str(e)}", exc_info=True)
        sentry_sdk.capture_exception(e)
        return jsonify({"error": "An unexpected error occurred"}), HTTP_500_INTERNAL_SERVER_ERROR


@api.route("/get_discount", methods=["POST"])
@limiter.limit(RATE_LIMIT_STANDARD)
def get_discount():
    """Get a discount for the user."""
    try:
        inputs = GetRerollDiscountInput(request)
        if not inputs.validate():
            sentry_sdk.capture_message(inputs.errors, level="warning")
            return jsonify({"error": "Invalid input", "messages": inputs.errors}), HTTP_400_BAD_REQUEST
        
        data = request.get_json()

        device_id = data.get("device_id")
        user_lat = data.get("latitude")
        user_long = data.get("longitude")
        user_timezone = data.get("timezone")
        category = data.get("category")

        if not user_lat or not user_long:
            logger.warning("No location available in get_discount request")
            return return_generic_error()
        
        user = User.query.filter_by(device_id=device_id).first()

        if not user:
            user = User(device_id=device_id, timezone=user_timezone)
            db.session.add(user)
            db.session.flush()
        else:           
            if user.claimed_today:
                logger.warning(f"User already claimed and tried rolling again: {device_id}")
                return return_generic_error()

            if user.rerolls <= 0:
                logger.info(
                    f"User {user.id} has no rerolls left and pinged get discount endpoint."
                )
                return return_generic_error()
            
            previous_claim = Claimed.query.filter_by(
                claimed_by=user.id, valid=True, claimed=None
            ).first()

            if previous_claim:
                return render_voucher(
                    Discount.query.get(previous_claim.discount_id),
                    user,
                    previous_claim.selected_category,
                )

        discount = get_random_discount(user_lat, user_long, category=category)

        if not discount:
            logger.warning("No discounts available for user location")
            return jsonify(
                {
                    "error": "No discounts available",
                    "message": "No discounts available. Please try again later.",
                }
            )

        claimed = Claimed(
            claimed_by=user.id,
            discount_id=discount.id,
            user_timezone=user_timezone,
            selected_category=category,
        )
        db.session.add(claimed)

        if not discount.unlimited_use:
            discount.remaining -= 1
            if discount.remaining <= 0:
                discount.available = False

        db.session.commit()

        return render_voucher(discount, user, claimed.selected_category)
    except Exception as e:
        logger.error(f"Error in get_discount: {str(e)}", exc_info=True)
        sentry_sdk.capture_exception(e)
        return jsonify({"error": "An unexpected error occurred"}), HTTP_500_INTERNAL_SERVER_ERROR


@api.route("/reroll", methods=["POST"])
@limiter.limit(RATE_LIMIT_STANDARD)
def reroll():
    """Reroll for a new discount."""
    try:
        inputs = GetRerollDiscountInput(request)
        if not inputs.validate():
            sentry_sdk.capture_message(inputs.errors, level="warning")
            return jsonify({"error": "Invalid input", "messages": inputs.errors}), HTTP_400_BAD_REQUEST
        
        data = request.get_json()
        device_id = data.get("device_id")
        user_lat = data.get("latitude")
        user_long = data.get("longitude")
        user_timezone = data.get("timezone")
        category = data.get("category")

        user = User.query.filter_by(device_id=device_id).first()
        if not user:
            logger.warning(f"User not found for device_id: {device_id}")
            return return_generic_error()

        if user.claimed_today:
            logger.warning(f"User already claimed and tried rolling again: {device_id}")
            return return_generic_error()

        if user.rerolls <= 0:
            logger.info(f"User {user.id} has no rerolls left")
            previous_claim = Claimed.query.filter_by(
                claimed_by=user.id, valid=True, claimed=None
            ).first()
            if previous_claim:
                discount = Discount.query.get(previous_claim.discount_id)
                return render_voucher(discount, user, previous_claim.selected_category)
            return return_generic_error()

        previous_claim = Claimed.query.filter_by(
            claimed_by=user.id, valid=True, claimed=None
        ).first()
        if previous_claim:
            previous_discount = Discount.query.get(previous_claim.discount_id)
            if not previous_discount.unlimited_use:
                previous_discount.remaining += 1
                if previous_discount.remaining > 0:
                    previous_discount.available = True

        discount = get_random_discount(
            user_lat,
            user_long,
            previous_claim.discount_id if previous_claim else None,
            category=category,
        )

        if not discount:
            logger.warning("No other discounts available for reroll")
            return jsonify(
                {
                    "error": "No discounts available",
                    "message": "No other discounts available. Please try again later or claim the current discount.",
                }
            )

        if not discount.unlimited_use:
            discount.remaining -= 1
            if discount.remaining <= 0:
                discount.available = False

        if previous_claim:
            previous_claim.claimed = False
            previous_claim.valid = False

        claimed = Claimed(
            claimed_by=user.id,
            discount_id=discount.id,
            user_timezone=user_timezone,
            selected_category=category,
        )

        db.session.add(claimed)
        user.rerolls -= 1
        db.session.commit()

        return render_voucher(discount, user, claimed.selected_category)
    except Exception as e:
        logger.error(f"Error in reroll: {str(e)}", exc_info=True)
        sentry_sdk.capture_exception(e)
        return jsonify({"error": "An unexpected error occurred"}), HTTP_500_INTERNAL_SERVER_ERROR


@api.route("/claim_discount", methods=["POST"])
@limiter.limit(RATE_LIMIT_STANDARD)
def claim_discount():
    """Claim a discount for the user."""
    try:
        inputs = ClaimDiscountInput(request)
        if not inputs.validate():
            sentry_sdk.capture_message(inputs.errors, level="warning")
            return jsonify({"error": "Invalid input", "messages": inputs.errors}), HTTP_400_BAD_REQUEST
        
        data = request.get_json()
        device_id = data.get("device_id")

        user = User.query.filter_by(device_id=device_id).first()
        if not user:
            logger.warning(f"User not found for device_id: {device_id}")
            return return_generic_error()

        if user.claimed_today:
            logger.warning(f"User already claimed and tried rolling again: {device_id}")
            return return_generic_error()

        claimed = Claimed.query.filter_by(
            claimed_by=user.id, claimed=None, valid=True
        ).first()

        if not claimed:
            logger.warning(f"No unclaimed discount found for user {user.id}")
            return return_generic_error()

        discount = claimed.discount

        claimed.claimed = True
        claimed.claim_time = datetime.now(timezone.utc)

        user.claimed_today = True
        db.session.commit()

        return render_claimed_voucher(discount, claimed)
    except Exception as e:
        logger.error(f"Error in claim_discount: {str(e)}", exc_info=True)
        sentry_sdk.capture_exception(e)
        return jsonify({"error": "An unexpected error occurred"}), HTTP_500_INTERNAL_SERVER_ERROR


@api.route("/get_stores", methods=["GET"])
def get_stores():
    """Get a list of stores with available discounts."""
    try:
        return jsonify({"stores": get_stores_with_discounts()})
    except Exception as e:
        logger.error(f"Error in get_stores: {str(e)}", exc_info=True)
        sentry_sdk.capture_exception(e)
        return return_generic_error()


@api.route("/autocomplete", methods=["POST"])
@limiter.limit(RATE_LIMIT_AUTOCOMPLETE)
@limiter.limit(RATE_LIMIT_AUTOCOMPLETE_DAILY)
def autocomplete():
    """Handle autocomplete requests for location search."""
    try:
        inputs = AutocompleteInput(request)

        if not inputs.validate():
            sentry_sdk.capture_message(inputs.errors, level="warning")
            return jsonify({"error": "Invalid input", "messages": inputs.errors}), HTTP_400_BAD_REQUEST
        
        data = request.get_json()
        query = data.get("query")

        google_api_key = current_app.config["GOOGLE_PLACES_API_KEY"]
        url = f"https://maps.googleapis.com/maps/api/place/autocomplete/json?input={query}&key={google_api_key}&components=country:au"

        response = requests.get(url)
        response.raise_for_status()
        results = response.json()["predictions"]

        return jsonify(results)
    except requests.RequestException as e:
        logger.error(f"Error fetching autocomplete results: {str(e)}", exc_info=True)
        sentry_sdk.capture_exception(e)
        return jsonify({"error": "Unable to fetch autocomplete results"})


@api.route("/place_details", methods=["POST"])
@limiter.limit(RATE_LIMIT_PLACE_DETAILS)
def place_details():
    """Get details for a specific place."""
    try:
        inputs = PlaceDetailsInput(request)
        
        if not inputs.validate():
            sentry_sdk.capture_message(inputs.errors, level="warning")
            return jsonify({"error": "Invalid input", "messages": inputs.errors}), HTTP_400_BAD_REQUEST

        data = request.get_json()

        place_id = data.get("place_id")

        google_api_key = current_app.config["GOOGLE_PLACES_API_KEY"]
        url = f"https://maps.googleapis.com/maps/api/place/details/json?place_id={place_id}&fields=geometry&key={google_api_key}"

        response = requests.get(url)
        response.raise_for_status()
        result = response.json()["result"]
        lat = result["geometry"]["location"]["lat"]
        lng = result["geometry"]["location"]["lng"]
        return jsonify({"lat": lat, "lng": lng})
    except requests.RequestException as e:
        logger.error(f"Error fetching place details: {str(e)}", exc_info=True)
        sentry_sdk.capture_exception(e)
        return jsonify({"error": "Unable to fetch place details"})


@api.route("/redeem/<token>", methods=["POST"])
def redeem_voucher(token):
    """Redeem a voucher."""
    try:
        claimed = Claimed.query.filter_by(token=token).first()

        if not claimed:
            logger.warning(f"Claimed voucher not found for token: {token}")
            return jsonify(
                {
                    "error": "No voucher found",
                    "message": "No claimed voucher found for user.",
                }
            )

        if claimed.redeemed:
            return jsonify(
                {
                    "error": "Already Redeemed",
                    "message": "Voucher is already redeemed.",
                }
            )

        if not claimed.valid:
            return jsonify(
                {
                    "error": "Not valid.",
                    "message": "Looks like this voucher is past the expiry time.",
                }
            )

        claimed.redeemed = True
        claimed.redeemed_time = datetime.now(timezone.utc)
        claimed.valid = False
        db.session.commit()
        return jsonify(
            {
                "alert": "Voucher redeemed.",
                "message": "Voucher redeemed successfully.",
            }
        )
    except SQLAlchemyError as e:
        logger.error(f"Database error in redeem_voucher: {str(e)}", exc_info=True)
        sentry_sdk.capture_exception(e)
        db.session.rollback()
        return jsonify(
            {
                "error": "Database error.",
                "message": "Error when redeeming, please try again or contact admins.",
            }
        )
    except Exception as e:
        logger.error(f"Unexpected error in redeem_voucher: {str(e)}", exc_info=True)
        sentry_sdk.capture_exception(e)
        return jsonify(
            {
                "error": "Error.",
                "message": "Error when redeeming, please try again or contact admins.",
            }
        )
