function processAjaxErrors(error_dict) {
    for (var key of Object.keys(error_dict)) {
        M.toast({
            html: key + ': ' + error_dict[key]
        });
        var form_element = $("#" + key).parent();
        var prev_helper_text = form_element.find('.helper-text');
        var new_error = $(
            '<span class="helper-text red-text left" style="display:none;">' +
            error_dict[key] + '</span>');

        if (prev_helper_text.length !== 0) {
            prev_helper_text.fadeOut(function () {
                prev_helper_text.remove();
                form_element.append(new_error);
                new_error.fadeIn();
            })
        } else {
            form_element.append(new_error);
            new_error.fadeIn();
        }
    }
}

function removeErrors() {
    $(".helper-text").fadeOut(function () {
        $(".helper-text").remove();
    })
}

function sendAjaxRequest(form_url, form_data, modal, error_text, successTimeoutFunc) {
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
                processAjaxErrors(error_dict);
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

    sendAjaxRequest(form_url, form_data, "#change-password", "Error Changing Password: ", successTimeoutFunc)
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

    sendAjaxRequest(form_url, form_data, "#change-username", "Error Changing Username: ", successTimeoutFunc)
});