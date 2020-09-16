var form = document.querySelector('.pageclip-form')
Pageclip.form(form, {
    onSubmit: function (event) {

    },
    onResponse: function (error, response) {
        console.log(response)
        console.log(error.toString())
        return false;
    }
})

// $("#contact-form").submit(function (e) {
//     e.preventDefault(); // avoid to execute the actual submit of the form.

//     var form = $(this);
//     form_url = form.attr('action');

//     form_data = form.serialize(); // serializes the form's elements

//     $.ajax({
//         type: "POST",
//         url: form_url,
//         data: form_data,
//         success: function (data) {
//             removeErrors();
//             M.toast({
//                 html: "Your message has been sent."
//             });
//             setTimeout(function() {
//                 M.toast({
//                     html: "Redirecting home..."
//                 });
//                 window.location.replace("/");
//             }, 2000);
//         },
//         error: function (request, status, error) {
//             if (request.status == "400") {
//                 error_dict = JSON.parse(request.responseText);
//                 processAjaxErrors(error_dict["errors"]);
//             } else {
//                 removeErrors();
//                 M.toast({
//                     html: "Error " + request.status + ": Your message failed to send. " + request.responseText
//                 });
//             }
//         }
//     });
// });