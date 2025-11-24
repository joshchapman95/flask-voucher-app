import {showModal } from './app.js';


$(document).ready(function() {
    const url = new URL(window.location.href);
    const token = url.pathname.split('/').pop();
    $('#redeem-btn').on('click', function() {
        $.ajax({
            url: `/api/redeem/${token}`,
            type: 'POST',
            success: function(response) {
                if (response.alert) {
                    showModal(response.message);
                } else {
                    showModal(response.message)
                }
            },
            error: function() {
                showModal("Error redeeming voucher. Please try again.");
            }
        });
    });
});