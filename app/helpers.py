import math
import random
import logging
from flask import jsonify, render_template, current_app, url_for
from datetime import datetime, timedelta
from sqlalchemy import and_
from geopy.distance import geodesic
import qrcode
from qrcode.image.pil import PilImage
from app import db
from app.models import User, Discount, Store, Claimed
from app.constants import (
    EARTH_DEGREE_KM,
    LATITUDE_MAX,
    LONGITUDE_MAX,
    QR_CODE_EXPIRY_SECONDS,
    CACHE_TIMEOUT_SECONDS,
    QR_BOX_SIZE,
    QR_BORDER_SIZE,
    HTTP_500_INTERNAL_SERVER_ERROR
)
from io import BytesIO
import json
import base64
import pytz
import sentry_sdk

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def get_random_discount(user_lat, user_long, previous_voucher=None, category=None):
    """Get a random discount within the specified distance from the user's location."""
    try:
        max_distance = current_app.config['VOUCHER_DISTANCE']

        # Calculate bounding box for initial filtering
        # 1 degree of latitude is approximately 111 km
        lat_change = max_distance / EARTH_DEGREE_KM
        
        # 1 degree of longitude is approximately 111 km * cos(latitude)
        
        if abs(user_lat) >= LATITUDE_MAX:
            long_change = LONGITUDE_MAX
        else:
            long_change = abs(max_distance / (EARTH_DEGREE_KM * math.cos(math.radians(user_lat))))

        min_lat = user_lat - lat_change
        max_lat = user_lat + lat_change
        min_long = user_long - long_change
        max_long = user_long + long_change

        query = Discount.query.filter(
            and_(Discount.available == True, Discount.id != previous_voucher)
        )
            
        if category and category.lower() != "any":
            query = query.filter(Discount.category == category)
        
        # Apply bounding box filter in SQL
        query = query.join(Store).filter(
            and_(
                Store.lat.between(min_lat, max_lat),
                Store.long.between(min_long, max_long)
            )
        )

        discounts = query.all()
  
        nearby_discounts = [
            d for d in discounts
            if calculate_distance(user_lat, user_long, d.store.lat, d.store.long) <= max_distance
            and (d.unlimited_use or d.remaining > 0)
        ]
        
        return random.choice(nearby_discounts) if nearby_discounts else None
    except Exception as e:
        logger.error(f"Error in get_random_discount: {str(e)}", exc_info=True)
        sentry_sdk.capture_exception(e)
        return None

def get_user_state(user_id, path=None):
    """Get the current state of the user."""
    try:
        if path and path.startswith('/redeem/'):
            token = path.split('/')[-1]
            claimed = Claimed.query.filter_by(token=token, redeemed=False).first()
            if claimed:
                return "redeem", claimed.discount, claimed
            return "home", None, None
        user = User.query.get(user_id)
        
        if not user:
            return "home", None, None
        
        claimed = (
            db.session.query(Claimed, Discount, Store)
            .join(Discount, Claimed.discount_id == Discount.id)
            .join(Store, Discount.store_id == Store.id)
            .filter(Claimed.claimed_by == user_id, Claimed.valid == True)
            .order_by(Claimed.roll_time.desc())
            .first()
        )

        if not claimed:
            return "redeemed" if user.claimed_today else "home", None, None
        
        claimed_entry, discount, store = claimed

        user_tz = pytz.timezone(user.timezone)
        current_time = datetime.now(user_tz)
        local_claim_time = claimed_entry.local_claim_time
        
        if claimed_entry.claimed is None:
    
            return "reroll", discount, claimed_entry
    
        if claimed_entry.claimed and not claimed_entry.redeemed:
            if local_claim_time:
                next_midnight = (local_claim_time + timedelta(days=1)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                if current_time >= next_midnight:
                    return "redeemed" if user.claimed_today else "home", None, None
                else:
                    return "voucher", discount, claimed_entry
            
        return "redeemed" if user.claimed_today else "home", None, None
    except Exception as e:
        logger.error(f"Error in get_user_state: {str(e)}", exc_info=True)
        sentry_sdk.capture_exception(e)
        return "error", None, None

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate the distance between two points."""
    return geodesic((lat1, lon1), (lat2, lon2)).km

def store_qr_code(token, qr_image):
    """Store QR code in Redis with 24-hour expiration."""
    try:
        buffered = BytesIO()
        qr_image.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        
        qr_data = json.dumps({
            'image': img_str,
            'format': 'PNG'
        })

        redis_client = current_app.config['REDIS_CLIENT']
        redis_client.setex(f"qr_code:{token}", QR_CODE_EXPIRY_SECONDS, qr_data)  
        
        return base64.b64decode(img_str)
    except Exception as e:
        logger.error(f"Error in store_qr_code: {str(e)}", exc_info=True)
        sentry_sdk.capture_exception(e)
        return None

def get_qr_code(token):
    """Retrieve QR code from Redis."""
    try:
        redis_client = current_app.config['REDIS_CLIENT']
        qr_data = redis_client.get(f"qr_code:{token}")
        if qr_data:
            qr_dict = json.loads(qr_data)
            return base64.b64decode(qr_dict['image'])
        return None
    except Exception as e:
        logger.error(f"Error in get_qr_code: {str(e)}", exc_info=True)
        sentry_sdk.capture_exception(e)
        return None
    
def get_stores_with_discounts():
    """Get a list of stores with available discounts."""
    cache_key = "stores_with_discounts"
    redis_client = current_app.config['REDIS_CLIENT']
    
    cached_result = redis_client.get(cache_key)
    
    if cached_result:
        return json.loads(cached_result)
    
    stores = db.session.query(Store).join(Discount).filter(Discount.available == True).distinct().all()
    store_list = [{"name": store.name} for store in stores]
    
    redis_client.setex(cache_key, CACHE_TIMEOUT_SECONDS, json.dumps(store_list)) 
    return store_list

def generate_qr_code(token):
    """Generate a QR code for a given token."""
    try:
        logger.info(f"Starting QR code generation for claimed discount: {token}")

        qr_url = url_for('main.redeem_voucher', token=token, _external=True)
        logger.debug(f"QR URL: {qr_url}")

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=QR_BOX_SIZE,
            border=QR_BORDER_SIZE,
        )
        qr.add_data(qr_url)
        qr.make(fit=True)

        img = qr.make_image(
            fill_color="black", back_color="#FFFFFF", image_factory=PilImage
        )

        image_string = store_qr_code(token, img)

        return image_string
    except Exception as e:
        logger.error(f"Error in generate_qr_code: {str(e)}", exc_info=True)
        sentry_sdk.capture_exception(e)
        return None

def render_voucher(discount, user, category):
    """Render the voucher template."""
    try:
        rendered_html = render_template("voucher.html", discount=discount, user=user, category=category)
        return jsonify({"html": rendered_html, "is_home": False})
    except Exception as e:
        logger.error(f"Error in render_voucher: {str(e)}", exc_info=True)
        sentry_sdk.capture_exception(e)
        return jsonify({"error": "Failed to render voucher"}), HTTP_500_INTERNAL_SERVER_ERROR

def render_claimed_voucher(discount, claimed):
    """Render the claimed voucher template."""
    try:
        qr_img = get_qr_code(claimed.token)
        
        if not qr_img:
            qr_img = generate_qr_code(claimed.token)
        
        if qr_img:
            qr_img_url = f"data:image/png;base64,{base64.b64encode(qr_img).decode()}"
        else:
            raise ValueError("Failed to generate or retrieve QR code")

        rendered_html = render_template("claimed.html", discount=discount, qr_img_url=qr_img_url, token=claimed.token, expiry_time=claimed.local_expiry_time)
        return jsonify({"html": rendered_html, "is_home": False})
    except Exception as e:
        logger.error(f"Error in render_claimed_voucher: {str(e)}", exc_info=True)
        sentry_sdk.capture_exception(e)
        return jsonify({"error": "Failed to render claimed voucher"}), HTTP_500_INTERNAL_SERVER_ERROR

def render_home(categories):
    """Render the home template."""
    try:
        return jsonify({"html": render_template("home.html", categories=categories), "is_home": True})
    except Exception as e:
        logger.error(f"Error in render_home: {str(e)}", exc_info=True)
        sentry_sdk.capture_exception(e)
        return jsonify({"error": "Failed to render home page"}), HTTP_500_INTERNAL_SERVER_ERROR

def render_redeem_page(discount, token):
    """Render the redeem voucher template."""
    try:
        return render_template("redeem.html", discount=discount, token=token)
    except Exception as e:
        logger.error(f"Error in render_redeemed: {str(e)}", exc_info=True)
        sentry_sdk.capture_exception(e)
        return jsonify({"error": "Failed to render redeemed page"}), HTTP_500_INTERNAL_SERVER_ERROR
    
def render_redeemed():
    """Render the redeemed voucher template."""
    try:
        return jsonify({"html": render_template("voucher_redeemed.html"), "is_home": False})
    except Exception as e:
        logger.error(f"Error in render_redeemed: {str(e)}", exc_info=True)
        sentry_sdk.capture_exception(e)
        return jsonify({"error": "Failed to render redeemed page"}), HTTP_500_INTERNAL_SERVER_ERROR
    
def return_generic_error():
    """Return a generic error response."""
    return jsonify(
                {
                    "error": "No location available",
                    "message": "Looks like we ran into an error. Try refreshing your browser or contacting us at the email below if the issue continues."
                }
            )
