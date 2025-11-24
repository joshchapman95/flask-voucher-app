from flask_inputs import Inputs
from wtforms import validators as v
from app.constants import (
    MAX_STRING_LENGTH,
    LATITUDE_MIN,
    LATITUDE_MAX,
    LONGITUDE_MIN,
    LONGITUDE_MAX,
    CATEGORY_STRING_LENGTH
)

class AutocompleteInput(Inputs):
    """Validator for autocomplete input."""
    json = {
        'query': [v.DataRequired(), v.Length(min=1, max=MAX_STRING_LENGTH)]
    }

class PlaceDetailsInput(Inputs):
    """Validator for place details input."""
    json = {
        'place_id': [v.DataRequired(), v.Length(max=MAX_STRING_LENGTH)]
    }

class InitialLoadInput(Inputs):
    """Validator for initial load input."""
    json = {
        'device_id': [v.DataRequired(), v.Length(max=MAX_STRING_LENGTH)],
        'timezone': [v.DataRequired(), v.Length(max=MAX_STRING_LENGTH)]
    }

class GetRerollDiscountInput(Inputs):
    """Validator for reroll/get discount input."""
    json = {
        'device_id': [v.DataRequired(), v.Length(max=MAX_STRING_LENGTH)],
        'latitude': [v.DataRequired(), v.NumberRange(min=LATITUDE_MIN, max=LATITUDE_MAX)],
        'longitude': [v.DataRequired(), v.NumberRange(min=LONGITUDE_MIN, max=LONGITUDE_MAX)],
        'timezone': [v.DataRequired(), v.Length(max=MAX_STRING_LENGTH)],
        'category': [v.Optional(), v.Length(max=CATEGORY_STRING_LENGTH)]
    }

class ClaimDiscountInput(Inputs):
    """Validator for claiming discount input."""
    json = {
        'device_id': [v.DataRequired(), v.Length(max=MAX_STRING_LENGTH)]
    }
