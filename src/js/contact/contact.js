var form = document.querySelector('.pageclip-form')
Pageclip.form(form, {
    onResponse: function (error, response) {
        if (response != null && response.data == "ok") {
            M.toast({
                html: "Your message has been sent."
            });
            setTimeout(function() {
                M.toast({
                    html: "Redirecting home..."
                });
            }, 1700);
            setTimeout(function() {
                window.location.replace("/");
            }, 2000);
        } else if (error != null) {
            M.toast({
                html: "Your message failed to send. " + error.toString()
            });
        } else {
            M.toast({
                html: "Your message failed to send. An unknown error occurred."
            });
        }
        return false;
    }
})
