$(document).ready(function () {
    var logo = document.getElementById('logo');
    if (logo) {
        logo.style.display = 'none';
    } else {
        console.error('Logo element not found');
    }
    function updateCountdown() {
        const now = new Date();
        const midnight = new Date(now);
        midnight.setHours(24, 0, 0, 0);
        
        const timeLeft = midnight - now;

        const hours = Math.floor(timeLeft / (1000 * 60 * 60));
        const minutes = Math.floor((timeLeft % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((timeLeft % (1000 * 60)) / 1000);

        const countdownValue = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
        
        document.getElementById('countdown').innerHTML = countdownValue;
    }

    updateCountdown();
    setInterval(updateCountdown, 1000);
});