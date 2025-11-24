from flask import Blueprint, render_template, request
from app.helpers import render_redeem_page
from app.models import Claimed

main = Blueprint('main', __name__)

@main.route('/redeem/<token>')
def redeem_voucher(token):
    """Redeem a voucher via token."""
    claimed = Claimed.query.filter_by(token=token, redeemed=False).first()
    if claimed:
        initial_content = render_redeem_page(claimed.discount, token)
        return render_template('layout.html', initial_content=initial_content)
    return render_template('layout.html')

@main.route('/', defaults={'path': ''})
@main.route('/<path:path>')
def catch_all(path):
    """Catch all routes and render the layout."""
    return render_template('layout.html')
