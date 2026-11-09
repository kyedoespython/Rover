/* 
get the form id in the auth page
use event listener to use the function instead of standard browser action
use e as the event object
use async to wait for a request
*/
document.getElementById("resendForm").addEventListener("submit", async (e) => {
    e.preventDefault(); // 
    
    const btn = document.getElementById("resendBtn"); // var to store button via id
    const countdownText = document.getElementById("CountDownText"); // var to store the countdown span
    
    // find input name="csrf_token" , .value fetches the string of the actual csrf token
    const csrfToken = document.querySelector('input[name="csrf_token"]').value;

    btn.disabled = true; // disable the button straight away to limit request to 1 request

    // error handle
    try {
        // use the url, method as POST, header containing the csrf token
        // await = pause untill server responds then fetch
        const response = await fetch('/auth/Resend_Auth', {
            method: 'POST', // method has to be specified here otherwise defaults to GET request meaning flask error 405 
            headers: {
                'X-CSRFToken': csrfToken // header name for ajax request
            }
        });

        // check if the response received is true / ok to proceed
        if (response.ok) {
            // begin a 10 minute countdown before the button is unlocked
            let timeLeft = 600;

            // runs the function every second, id of the repeating timer is stored in 'const timer variable'
            const timer = setInterval(() => {
                const mins = Math.floor(timeLeft / 60); // 600 divided by 60 = 10
                const secs = timeLeft % 60;

                // give a MM:SS format / minutes and seconds
                // text content sets the text inside span
                // use .toString() method to use as a string method
                // .padStart(2, '0') is used to make the time visual two chars wide adding a leading 0 if needed (0:05 instead of 0:5)
                countdownText.textContent = `Wait ${mins}:${secs.toString().padStart(2, '0')}`;
                timeLeft--; // decrement time - 1
                
                // see if time left is 0 meaning time is up
                // use clear interval with timer as arg to stop the repeating function
                if (timeLeft < 0) {
                    clearInterval(timer);
                    btn.disabled = false; // re-enable the button
                    countdownText.textContent = ""; // clear the countdown text
                }
            }, 1000); // 1 second delay between runs
        }
    }
    
    // catch any error
    // if fetch fails
    // then re-enable the button
    catch (error) {
        console.error(error);
        btn.disabled = false;
    }
}); // close addEventListener