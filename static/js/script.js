document.addEventListener("DOMContentLoaded", function () {

    console.log("JimTask Earners Loaded");

    const alerts = document.querySelectorAll(".alert");

    alerts.forEach(function(alert){
        setTimeout(function(){
            alert.style.display = "none";
        },5000);
    });

});
