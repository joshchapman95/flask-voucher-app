export function getLocation(callback) {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            position => callback(position.coords.latitude, position.coords.longitude),
            error => {
                callback(null, null);
            }
        );
    } else {
        showModal("Geolocation is not supported by this browser. Search for your address in the address box.");
        callback(null, null);
    }
}


function updateHeader(isHome) {
    var headerContent = document.getElementById('header-content');
    var headerSpacer = document.getElementById('header-spacer');
  
    if (isHome) {
        headerContent.innerHTML = '<h1 class="welcome-text">Welcome to</h1>';
        headerContent.style.display = 'block';
        headerSpacer.style.display = 'none';
    } else {
        headerContent.innerHTML = '';
        headerContent.style.display = 'none';
        headerSpacer.style.display = 'block';
    }
}
export function showModal(message) {
    const modal = document.getElementById('customModal');
    const modalMessage = document.getElementById('modalMessage');
    modalMessage.textContent = message;
    modal.classList.add('show');
}

function hideModal() {
    const modal = document.getElementById('customModal');
    modal.classList.remove('show');
}


document.querySelector('.close-button').addEventListener('click', hideModal);


window.addEventListener('click', function (event) {
    const modal = document.getElementById('customModal');
    if (event.target === modal) {
        hideModal();
    }
});


export function loadContent(url, data = {}) {
    $.ajax({
        url: url,
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(data),
        success: function (response) {
            if (response.error || response.alert) {
                showModal(response.message)
                return;
            }
            $('#content').html(response.html);
            updateHeader(response.is_home);
        },
        error: function () {
            $('#content').html('<p>Error loading content.</p>');
            updateHeader(response.is_home);
        }
    });
}

async function hashString(str) {
    const encoder = new TextEncoder();
    const data = encoder.encode(str);
    const hashBuffer = await crypto.subtle.digest('SHA-256', data);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}

async function getIpAddress() {
    const response = await fetch('https://api.ipify.org?format=json');
    const data = await response.json();
    return data.ip;
}

export async function getDeviceId() {
    let deviceId = localStorage.getItem('deviceId');
    const userAgent = navigator.userAgent;

    if (!deviceId) {
        try {
            const ipAddress = await getIpAddress();
            const combinedString = `${ipAddress}|${userAgent}`;
            deviceId = await hashString(combinedString);
            localStorage.setItem('deviceId', deviceId);
        } catch (error) {
            showModal("Looks like we ran into an error :(. Try refreshing your browser or contacting us at the email below if the issue continues.")
            return null
        }
    }
    return deviceId;
}


$(document).ready(function () {
    function initialLoad() {
        let path = window.location.pathname;
        if (path.startsWith('/redeem/')) {
   
            updateHeader(false);
        } else {
            getDeviceId().then(deviceId => {
                let timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
                loadContent('/api/initial_load', {
                    device_id: deviceId,
                    timezone: timezone
                });
            });
        }
    }
    initialLoad();

 
    window.onpopstate = function(event) {
        initialLoad();
    };

});