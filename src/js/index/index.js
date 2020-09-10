$(document).ready(function () {
    var form_data;
    var form_url;
    var last_prediction_time;
    var last_zip_code;
    var zip_code;
    var geolocated_zip_code;
    var progressBarLongTimeNotificationTimers = [];
    var no_geolocation = false;
    var lastRequest;

    $("#predict-form-submit-btn").removeClass("disabled");

    function update_zip_code(new_zip_code) {
        $("#zip_code").val(new_zip_code);
        $("#zip_code").parent().children("label").addClass("active");
    }

    function geolocationSuccess(position) {
        const latitude = position.coords.latitude;
        const longitude = position.coords.longitude;

        $.ajax({
            type: "POST",
            url: "/reverse-geocode",
            data: JSON.stringify({
                "latitude": latitude,
                "longitude": longitude
            }),
            contentType: "application/json",
            success: function (data) {
                geolocated_zip_code = data;
                update_zip_code(data);
                M.toast({
                    html: 'Location successfully determined.'
                });
            },
            error: function (request, status, error) {
                M.toast({
                    html: 'Error During Automatic ZIP Code Detection: ' + request.responseText
                });
            },
            complete: function (request, status) {
                $("#get-location-icon").text("my_location").removeClass("icn-spinner");
            }
        });
    }

    function geolocationError() {
        no_geolocation = true;
        M.toast({
            html: 'Could not determine your location. Please enter your zip code manually.'
        });
        $("#get-location-icon").text("location_disabled").removeClass("icn-spinner");
    }

    $("#get-location-icon").on("click", function () {
        if (geolocated_zip_code) {
            update_zip_code(geolocated_zip_code);
            M.toast({
                html: 'Location successfully determined.'
            });
        } else if (navigator.geolocation) {
            if (no_geolocation) {
                geolocationError();
            } else {
                $("#get-location-icon").text("sync").addClass("icn-spinner");
                navigator.geolocation.getCurrentPosition(geolocationSuccess, geolocationError);
            }
        } else {
            M.toast({
                html: 'Your browser does not support geolocation. Please enter your zip code manually.'
            });
            $("#get-location-icon").text("location_disabled")
        }
    });

    $("#predict-form").submit(function (e) {

        e.preventDefault(); // avoid to execute the actual submit of the form.

        $("#predict-form-submit-btn").addClass("disabled")

        var form = $(this);
        form_url = form.attr('action');
        zip_code = form.serializeArray()[0].value;

        form_data = form.serialize(); // serializes the form's elements

        sendPredictRequest(form_data, zip_code, form_url);
    });

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

    function successHelper(extra_text = "") {
        M.toast({
            html: 'Prediction Successful!' + extra_text
        });
        $(".helper-text").fadeOut(function () {
            $(".helper-text").remove();
        })
    }

    function animateProgressBar(duration, end_func = false) {
        progressBarLongTimeNotificationTimers.push(setTimeout(function () {
            M.toast({
                html: 'The AI engine is taking an abnormally long time. Please wait...'
            });
        }, duration * 1.30));
        progressBarLongTimeNotificationTimers.push(setTimeout(function () {
            M.toast({
                html: 'Diagnosing potential problem...'
            });
        }, duration * 2));
        progressBarLongTimeNotificationTimers.push(setTimeout(function () {
            M.toast({
                html: 'Giving up in 5 seconds...'
            });
        }, duration * 2.7));
        progressBarLongTimeNotificationTimers.push(setTimeout(function () {
            M.toast({
                html: 'Prediction Canceled'
            });
            lastRequest.abort()
        }, duration * 2.7 + 5000));
        $("#nav-progress-bar").fadeIn(0)
        $("#nav-progress-bar").css({"width": "100%", "transition": duration + "ms linear"})
        if (end_func) {
            setTimeout(end_func, duration);
        }
    }

    function clearIntervals(intervals) {
        intervals.forEach(function(item, index, array) {
            window.clearInterval(item)
        })
        progressBarLongTimeNotificationTimers = []
    }

    function resetProgressBar() {
        clearIntervals(progressBarLongTimeNotificationTimers);
        $("#nav-progress-bar").fadeOut(function () {
            $("#nav-progress-bar").css({"width": "0", "transition": "1ms linear"});
        });
    }

    function stopAnimateProgressBar() {
        $("#nav-progress-bar").css("width", $("#nav-progress-bar").css("width"))
        setTimeout(function () {
            $("#nav-progress-bar").css({"width": "100%", "transition": "200ms linear"});
        }, 1);
        
        resetProgressBar();
    }

    function sendPredictRequest(form_data, zip_code, form_url) {
        current_time = new Date();
        // 600000 milliseconds is 10 minutes
        if (current_time - last_prediction_time < 600000 && zip_code == last_zip_code) {
            $("#predict-form-submit-btn").removeClass("disabled");
            successHelper(extra_text = " New weather data is obtained hourly.");
            $("#predict-panel").fadeOut("slow", function () {
                $("#results-panel").fadeIn("slow");
            });
            animateProgressBar(200, resetProgressBar);
            return;
        }

        animateProgressBar(10000);
        $("#predict-form-submit-btn").fadeOut(function () {
            $("#predict-form-btn-loader").fadeIn();
        });

        lastRequest = $.ajax({
            type: "POST",
            url: form_url,
            data: form_data,
            success: function (data) {
                data = JSON.parse(data)
                last_prediction_time = new Date(); // Only update the prediction time on success
                last_zip_code = zip_code;
                stopAnimateProgressBar();
                if (data.weather_text == "summer") {
                    extra_text = " It's the summer. There is no chance of a snow day since there is no school."
                } else {
                    extra_text = ""
                }
                successHelper(extra_text);
                createResults(data);
            },
            error: function (request, status, error) {
                stopAnimateProgressBar();
                $("#predict-form-submit-btn").removeClass("disabled")
                if (request.status == "400") {
                    error_dict = JSON.parse(request.responseText);
                    processAjaxErrors(error_dict);
                } else if (request.status == "429") {
                    M.toast({
                        html: 'You\'re sending predictions too fast! Slow down.'
                    });
                } else {
                    if (request.responseText == null) {
                        errorMessage = "Unknown Cause";
                    } else {
                        errorMessage = request.responseText + ". We have been notified of this issue.";
                    }

                    M.toast({
                        html: 'Error During Prediction: ' + errorMessage
                    });
                }
            },
            complete: function (request, status) {
                $("#predict-form-btn-loader").stop().fadeOut(function () {
                    $("#predict-form-submit-btn").stop().fadeIn();
                })
            }
        });
    }

    function push_date_to_weekday(date) {
        while (date.getDay() === 6 || date.getDay() === 0) {
            date.setDate(date.getDate() + 1);
        }
    }

    function createWeekDates() {
        const today = new Date();
        if (today.getHours() >= 12) {
            today.setDate(today.getDate() + 1);
        }

        push_date_to_weekday(today);
        const tomorrow = new Date();
        tomorrow.setDate(today.getDate() + 1);
        push_date_to_weekday(tomorrow);
        const thirdDay = new Date();
        thirdDay.setDate(tomorrow.getDate() + 1);
        push_date_to_weekday(thirdDay);

        const dates = [today.toLocaleDateString('en-us', {
            weekday: 'long'
        }), tomorrow.toLocaleDateString('en-us', {
            weekday: 'long'
        }), thirdDay.toLocaleDateString('en-us', {
            weekday: 'long'
        })];

        return dates;
    }

    function truncate(input, max_len) {
        if (input.length > max_len) {
            return input.substring(0, max_len) + '...';
        }
        return input;
    }

    function createResults(data) {
        $("#predict-panel").fadeOut("slow", function () {
            dates = createWeekDates();

            for (let i = 0; i < data.percentages.length; i++) {
                const element = data.percentages[i];
                
                $("#day-" + i + "-card").css("opacity", "1");

                var circleBarChance = $("#day-" + i + "-card .card-content svg path.circle");
                var circleTextChance = $("#day-" + i + "-card .card-content svg text.percentage");
                var cardTitle = $("#day-" + i + "-card span.card-title span.card-title-inner");
                var descriptionText = $("#day-" + i + "-percentage-text");
                
                if (element == -3) {
                    var moreInfoText = $("#day-" + i + "-more-info-text");

                    circleBarChance.hide();
                    circleTextChance.text("?");
                    cardTitle.text(dates[i]);
                    descriptionText.text("Unknown");
                    moreInfoText.text("We cannot make predictions this far in advance due to a lack of accurate forecast data.");
                } else {
                    circleBarChance.show().attr('stroke-dasharray',
                        element + ', 100');
                    circleTextChance.text(element + "%");
                    cardTitle.text(dates[i]);
                    descriptionText.text(element);
                }
            }

            if (data.weather_text == null || data.weather_text == "summer") {
                for (let i = 0; i < 3; i++) {
                    $("#day-" + i + "-text").html("");
                    $("#day-" + i + "-text-all").html("No additional information available.");
                }
            } else {
                for (let i = 0; i < data.weather_text.length; i++) {
                    const element = data.weather_text[i];
                    
                    new_html = "";
                    element.forEach(function (period, index) {
                        new_html += "<strong>" + period["name"] + "</strong>: ";
                        new_html += truncate(period["detailedForecast"], 100) + "<br>";
                    });
                    $("#day-" + i + "-text").html(new_html);

                    new_html = "";
                    element.forEach(function (period, index) {
                        new_html += "<strong>" + period["name"] + "</strong>: ";
                        new_html += period["detailedForecast"] + "<br>";
                    });
                    $("#day-" + i + "-text-all").html(new_html);
                }
            }

            window.scrollTo(0, 0);
            $("#results-panel").fadeIn("slow", function () {
                $("#predict-form-submit-btn").removeClass("disabled");
                for (let i = 0; i < data.percentages.length; i++) {
                    const element = data.percentages[i];
                    
                    if (element == -3) {
                        $("#day-" + i + "-card").css("opacity", "0.5");
                    }
                }
            });
        });
    }

    $("#help-form").submit(function (e) {

        e.preventDefault(); // avoid to execute the actual submit of the form.

        var form = $(this);
        help_form_url = form.attr('action');

        help_form_data = form.serialize(); // serializes the form's elements

        $.ajax({
            type: "POST",
            url: help_form_url,
            data: help_form_data,
            success: function (data) {
                M.toast({
                    html: 'Thank you! You will receive an email from us at 4:00pm.'
                });
                var model_instance = M.Modal.getInstance($("#help-improve"));
                model_instance.close();
                $("#help-improve-btn").fadeOut();
            },
            error: function (request, status, error) {
                if (request.status == "400") {
                    error_dict = JSON.parse(request.responseText);

                    processAjaxErrors(error_dict);
                } else if (request.responseText == "summer") {
                    M.toast({
                        html: "It's the summer. You can not submit improvement reports in the summer."
                    });
                } else {
                    M.toast({
                        html: 'Error submitting email: ' + request.responseText
                    });
                }
            }
        });
    });

    $("#go-back-btn").on("click", function () {
        $("#results-panel").fadeOut("slow", function () {
            $("#predict-panel").fadeIn("slow");
        });
    });
    $("#refresh-btn").on("click", function () {
        sendPredictRequest(form_data, zip_code, form_url);
    });
});