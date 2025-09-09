document.addEventListener("DOMContentLoaded", function () {
    let tabs = document.querySelectorAll(".nav-link");
    tabs.forEach(tab => {
        tab.addEventListener("click", function () {
            localStorage.setItem("activeTab", this.id);
        });
    });

    let activeTab = localStorage.getItem("activeTab");
    if (activeTab) {
        document.getElementById(activeTab).click();
    }
});
