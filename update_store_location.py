import requests
from app import create_app, db
from app.models import Store, Discount

def get_current_location():
    try:
        response = requests.get('http://ip-api.com/json/')
        data = response.json()
        if data['status'] == 'success':
            return data['lat'], data['lon']
        else:
            print("Could not fetch location via IP API.")
            return None
    except Exception as e:
        print(f"Error fetching location: {e}")
        return None

def update_store_location():
    app = create_app()
    with app.app_context():
        print("Fetching current location...")
        location = get_current_location()
        if not location:
            print("Failed to get location. Aborting update.")
            return
        
        lat, lon = location
        print(f"Detected Location: Lat {lat}, Long {lon}")
        
        # Check if a store exists
        store = Store.query.first()
        
        if not store:
            print("No store found in database. Creating a new store...")
            store = Store(
                name="Demo Store",
                website="https://www.example.com",
                lat=lat,
                long=lon
            )
            db.session.add(store)
            try:
                db.session.commit()
                print(f"Successfully created Store: {store.name} at {lat}, {lon}")
            except Exception as e:
                db.session.rollback()
                print(f"Error creating store: {e}")
                return
        else:
            print(f"Found Store: {store.name}. Updating location...")
            store.lat = lat
            store.long = lon
            try:
                db.session.commit()
                print(f"Successfully updated Store location to: {lat}, {lon}")
            except Exception as e:
                db.session.rollback()
                print(f"Error updating store: {e}")
                return

        # Add 3 Vouchers (Discounts) if they don't exist
        vouchers_data = [
            {
                "details": "Free Coffee",
                "category": "Drink",
                "remaining": 100,
                "unlimited_use": False
            },
            {
                "details": "20% Off All Items",
                "category": "Food",
                "remaining": 50,
                "unlimited_use": False
            },
            {
                "details": "Buy 1 Get 1 Free",
                "category": "Food",
                "remaining": 30,
                "unlimited_use": False
            }
        ]

        print("Checking/Creating vouchers...")
        for v_data in vouchers_data:
            # Check if this voucher already exists for the store
            existing_voucher = Discount.query.filter_by(
                store_id=store.id, 
                details=v_data['details']
            ).first()

            if not existing_voucher:
                print(f"Creating voucher: {v_data['details']}")
                new_voucher = Discount(
                    store_id=store.id,
                    details=v_data['details'],
                    category=v_data['category'],
                    remaining=v_data['remaining'],
                    unlimited_use=v_data['unlimited_use'],
                    available=True
                )
                db.session.add(new_voucher)
            else:
                print(f"Voucher already exists: {v_data['details']}")

        try:
            db.session.commit()
            print("Vouchers check complete.")
        except Exception as e:
            db.session.rollback()
            print(f"Error updating vouchers: {e}")

if __name__ == "__main__":
    update_store_location()
