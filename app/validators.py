from flask_inputs import Inputs
from wtforms import validators as v

class AutocompleteInput(Inputs):
    """Validator for autocomplete input."""
    json = {
        'query': [v.DataRequired(), v.Length(min=1, max=255)]
    }

class PlaceDetailsInput(Inputs):
    """Validator for place details input."""
    json = {
        'place_id': [v.DataRequired(), v.Length(max=255)]
    }

class InitialLoadInput(Inputs):
    """Validator for initial load input."""
    json = {
        'device_id': [v.DataRequired(), v.Length(max=255)],
        'timezone': [v.DataRequired(), v.Length(max=255)]
    }

class GetRerollDiscountInput(Inputs):
    """Validator for reroll/get discount input."""
    json = {
        'device_id': [v.DataRequired(), v.Length(max=255)],
        'latitude': [v.DataRequired(), v.NumberRange(min=-90, max=90)],
        'longitude': [v.DataRequired(), v.NumberRange(min=-180, max=180)],
        'timezone': [v.DataRequired(), v.Length(max=255)],
        'category': [v.Optional(), v.Length(max=25)]
    }

class ClaimDiscountInput(Inputs):
    """Validator for claiming discount input."""
    json = {
        'device_id': [v.DataRequired(), v.Length(max=255)]
    }
