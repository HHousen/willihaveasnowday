function sendAjaxRequest(form_url, form_data, modal, error_text, successTimeoutFunc, message_429) {
    $.ajax({
        type: "POST",
        url: form_url,
        data: form_data,
        success: function (data) {
            removeErrors();
            data = JSON.parse(data);
            M.toast({
                html: data
            });
            $(modal).modal('close');
            setTimeout(successTimeoutFunc, 1800);
        },
        error: function (request, status, error) {
            if (request.status == "400") {
                error_dict = JSON.parse(request.responseText);
                processAjaxErrors([error_dict]);
            } else if (request.status == "429") {
                M.toast({
                    html: message_429
                });
            } else {
                removeErrors();
                M.toast({
                    html: error_text + request.responseText
                });
            }
        }
    });
}

$("#change-password-form").submit(function (e) {
    e.preventDefault(); // avoid to execute the actual submit of the form.

    var form = $(this);
    form_url = form.attr('action');

    form_data = form.serialize(); // serializes the form's elements

    successTimeoutFunc = function() {
        M.toast({
            html: "Redirecting to login page..."
        });
        window.location.replace("/user/signin");
    }

    sendAjaxRequest(form_url, form_data, "#change-password", "Error Changing Password: ", successTimeoutFunc, "You can only change your password once per minute")
});

$("#change-username-form").submit(function (e) {
    e.preventDefault(); // avoid to execute the actual submit of the form.

    var form = $(this);
    form_url = form.attr('action');

    form_data = form.serialize(); // serializes the form's elements

    successTimeoutFunc = function() {
        M.toast({
            html: "Reloading..."
        });
        window.location.reload(true);
    }

    sendAjaxRequest(form_url, form_data, "#change-username", "Error Changing Username: ", successTimeoutFunc, "You can only change your username once every hour")
});

$("#receive-improve-emails-checkbox").change(function(){
    if($(this).is(':checked')) {
        data = 1
    } else {
        data = 0
    }

    $.ajax({
        type: "POST",
        url: "/user/improve-emails-toggle",
        contentType: "application/json",
        data: JSON.stringify({"state": data}),
        success: function (data) {
            data = JSON.parse(data);
            if (data == 1) {
                M.toast({
                    html: "You will now receive improve emails."
                });
            } else {
                M.toast({
                    html: "You will no longer receive improve emails."
                });
            }
        },
        error: function (request, status, error) {
            if (request.status == "429") {
                M.toast({
                    html: "You are changing this option too fast. Please slow down..."
                });
            } else {
                M.toast({
                    html: "Error Toggling Improve Emails: " + request.responseText
                });
            }
        }
    });
});