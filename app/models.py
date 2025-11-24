from app import db
from datetime import datetime, timezone, timedelta
import uuid, pytz


class User(db.Model):
    """User model."""
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(255), unique=True, nullable=False)
    rerolls = db.Column(db.Integer, nullable=False, default=2)
    timezone = db.Column(db.String(255), nullable=False)
    claimed_today = db.Column(db.Boolean, nullable=False, default=False)
    claimed_discounts = db.relationship("Claimed", backref="user", lazy=True)

    __table_args__ = (db.Index("idx_device_id", "device_id"),)

    def to_dict(self):
        """Convert object to dictionary."""
        return {
            "id": self.id,
            "device_id": self.device_id,
            "rerolls": self.rerolls,
            "timezone": self.timezone,
            "claimed_today": self.claimed_today,
        }


class Discount(db.Model):
    """Discount model."""
    __tablename__ = "discounts"
    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=False)
    details = db.Column(db.String(255), nullable=False)
    unlimited_use = db.Column(db.Boolean, nullable=False, default=False)
    remaining = db.Column(db.Integer, nullable=True)
    category = db.Column(db.String(50), nullable=False)
    available = db.Column(db.Boolean, nullable=False, default=True)
    claimed_discounts = db.relationship("Claimed", backref="discount", lazy=True)

    def to_dict(self):
        """Convert object to dictionary."""
        return {
            "id": self.id,
            "store_id": self.store_id,
            "details": self.details,
            "unlimited_use": self.unlimited_use,
            "remaining": self.remaining,
            "category": self.category,
            "available": self.available,
        }


class Store(db.Model):
    """Store model."""
    __tablename__ = "stores"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    website = db.Column(db.String(255), nullable=False)
    lat = db.Column(db.DECIMAL(9, 6), nullable=False)
    long = db.Column(db.DECIMAL(9, 6), nullable=False)
    discounts = db.relationship("Discount", backref="store", lazy=True)

    def to_dict(self):
        """Convert object to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'website': self.website,
            'lat': float(self.lat),
            'long': float(self.long)
        }


class Claimed(db.Model):
    """Claimed voucher model."""
    __tablename__ = "claimed"
    id = db.Column(db.Integer, primary_key=True)
    claimed = db.Column(db.Boolean, nullable=True, default=None)
    claimed_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    token = db.Column(
        db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4())
    )
    redeemed = db.Column(db.Boolean, nullable=False, default=False)
    selected_category = db.Column(db.String(50), nullable=False)
    discount_id = db.Column(db.Integer, db.ForeignKey("discounts.id"), nullable=False)
    roll_time = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    claim_time = db.Column(db.DateTime, nullable=True)
    redeemed_time = db.Column(db.DateTime, nullable=True)
    valid = db.Column(db.Boolean, default=True)
    user_timezone = db.Column(db.String(50), nullable=False)

    __table_args__ = (
        db.Index("idx_claimed_by_valid", "claimed_by", "valid"),
        db.Index("idx_roll_time", "roll_time"),
        db.Index("idx_token", "token"),
    )

    @property
    def local_roll_time(self):
        """Get local roll time."""
        return self.convert_to_local(self.roll_time)

    @property
    def local_claim_time(self):
        """Get local claim time."""
        return self.convert_to_local(self.claim_time) if self.claim_time else None

    @property
    def local_redeemed_time(self):
        """Get local redeemed time."""
        return self.convert_to_local(self.redeemed_time) if self.redeemed_time else None

    @property
    def local_expiry_time(self):
        """Get local expiry time."""
        if self.claim_time:
            expiry_time = self.claim_time + timedelta(hours=48)
            local_time = self.convert_to_local(expiry_time)
            return local_time.strftime("%d %b %Y, %I:%M %p")
        return None

    def convert_to_local(self, utc_time):
        """Convert UTC time to local time."""
        local_tz = pytz.timezone(self.user_timezone)
        return utc_time.replace(tzinfo=pytz.UTC).astimezone(local_tz)

    def to_dict(self):
        """Convert object to dictionary."""
        return {
            'id': self.id,
            'claimed': self.claimed,
            'claimed_by': self.claimed_by,
            'token': self.token,
            'redeemed': self.redeemed,
            'selected_category': self.selected_category,
            'discount_id': self.discount_id,
            'roll_time': self.roll_time.isoformat() if self.roll_time else None,
            'claim_time': self.claim_time.isoformat() if self.claim_time else None,
            'redeemed_time': self.redeemed_time.isoformat() if self.redeemed_time else None,
            'valid': self.valid,
            'user_timezone': self.user_timezone
        }
