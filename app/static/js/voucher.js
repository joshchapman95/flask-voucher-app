import { getLocation, loadContent } from './app.js';

$(document).ready(function () {
    let deviceId = localStorage.getItem('deviceId');
    let userLat = localStorage.getItem('userLat');
    let userLng = localStorage.getItem('userLng');
    let timezone = localStorage.getItem('userTimezone');

    function getUserLocation(callback) {
        if (userLat && userLng) {
            callback(parseFloat(userLat), parseFloat(userLng));
        } else {
            getLocation((lat, lng) => {
                userLat = lat;
                userLng = lng;
                localStorage.setItem('userLat', lat);
                localStorage.setItem('userLng', lng);
                callback(lat, lng);
            });
        }
    }

    $(document).on('click', '#claim-btn', function () {
        loadContent('/api/claim_discount', {
            device_id: deviceId,
            timezone: timezone
        });
    });

    $(document).on('click', '#tryagain-btn', function () {
        let category = $('#voucher-category').val();
        getUserLocation((lat, lng) => {
            loadContent('/api/reroll', {
                device_id: deviceId,
                latitude: lat,
                longitude: lng,
                timezone: timezone,
                category: category
            });
        });
    });
});