function processAjaxErrors(error_list) {
    error_list.forEach(function (error_dict, index) {
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
    });
}

function removeErrors() {
    $(".helper-text").fadeOut(function () {
        $(".helper-text").remove();
    })
}