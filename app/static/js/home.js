import { getLocation, loadContent, getDeviceId, showModal } from './app.js';

$(document).ready(function () {
    let selectedLocation = null;
    const $locationInput = $("#location-input");
    const defaultPlaceholder = "   USING CURRENT LOCATION ...";
    const $inputSymbol = $(".input-symbol");

    $('#see-stores-link').on('click', function(e) {
        e.preventDefault();
        $.ajax({
            url: '/api/get_stores',
            method: 'GET',
            success: function(data) {
                const storesList = $('#storesList');
                storesList.empty();
                data.stores.forEach(store => {
                    storesList.append(`<li>${store.name}</li>`);
                });
                $('#storesModal').addClass('show');
            },
            error: function(xhr, status, error) {
                console.error("Error fetching stores:", error);
                showModal("Error fetching stores. Please try again later.");
            }
        });
    });

    $('.close-button').on('click', function() {
        $('#storesModal').removeClass('show');
    });

    $(window).on('click', function(event) {
        if ($(event.target).hasClass('custom-modal')) {
            $('.custom-modal').removeClass('show');
        }
    });

    function updateLocationStatus() {
        if (selectedLocation) {
            $locationInput.css("border-color", "green");
        } else if ($locationInput.val() && !selectedLocation && $locationInput.val() != "   USING CURRENT LOCATION ...") {
            $locationInput.css("border-color", "red");
        } else {
            $locationInput.css("border-color", "black");
        }
    }

    $locationInput.autocomplete({
        source: function (request, response) {
            $.ajax({
                url: '/api/autocomplete',
                method: 'POST',
                data: JSON.stringify({
                    query: request.term,
                    components: 'country:au'
                }),
                contentType: 'application/json',
                success: function (data) {
                    response(data.map(item => ({
                        label: item.description,
                        value: item.place_id
                    })));
                }
            });
        },
        minLength: 3,
        select: function (event, ui) {
            event.preventDefault();
            $(this).val(ui.item.label);

            $.ajax({
                url: '/api/place_details',
                method: 'POST',
                data: JSON.stringify({ place_id: ui.item.value }),
                contentType: 'application/json',
                success: function (data) {
                    console.log("Selected location details:", data);
                    selectedLocation = {
                        lat: data.lat,  
                        lng: data.lng
                    };
                    console.log("Updated selectedLocation:", selectedLocation); 
                    updateLocationStatus();
                },
                error: function (xhr, status, error) {
                    console.error("Failed to fetch place details:", error);
                }
            });
        }
    });

    $locationInput.on('focus', function () {
        if ($(this).val() === defaultPlaceholder) {
            $(this).val('');
            $inputSymbol.hide();
        }
    });

    $locationInput.on('blur', function () {
        if ($(this).val() === '' || selectedLocation == null) {
            $(this).val(defaultPlaceholder);
            $inputSymbol.show();
            selectedLocation = null;
        }
        updateLocationStatus();
    });

    $locationInput.on('input', function () {
        if (selectedLocation) {
            selectedLocation = null;
        }
        updateLocationStatus();
    });


    updateLocationStatus();


    $('#generate-btn').on('click', function () {
        let selectedCategory = $('#category-select').val();
        let timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
        getDeviceId().then(deviceId => {
            if (selectedLocation) {
                if (selectedLocation.lat == null || selectedLocation.lng == null) {
                    showModal("App requires your location to find you great deals!")
                }
                else {
             
                    localStorage.setItem('userLat', selectedLocation.lat);
                    localStorage.setItem('userLng', selectedLocation.lng);
                    localStorage.setItem('userTimezone', timezone);
                    
                    loadContent('/api/get_discount', {
                        device_id: deviceId,
                        latitude: selectedLocation.lat,
                        longitude: selectedLocation.lng,
                        category: selectedCategory,
                        timezone: timezone
                    });
                }
            } else {
                getLocation((lat, lng) => {
                    if (lat == null || lng == null) {
                        showModal("App requires your location to find you great deals!")
                    }
                    else {
                
                        localStorage.setItem('userLat', lat);
                        localStorage.setItem('userLng', lng);
                        localStorage.setItem('userTimezone', timezone);
                        
                        loadContent('/api/get_discount', {
                            device_id: deviceId,
                            latitude: lat,
                            longitude: lng,
                            category: selectedCategory,
                            timezone: timezone
                        });
                    }
                });
            }
        });
    });
});
