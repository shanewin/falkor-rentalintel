document.addEventListener("DOMContentLoaded", function () {
    const applicantSelect = document.getElementById("applicant-select");

    if (!applicantSelect) {
        console.error("Applicant select dropdown not found.");
        return;
    }

    applicantSelect.addEventListener("change", function () {
        const applicantId = this.value;
        if (applicantId) {
            fetch(`/applicants/get-applicant-data/${applicantId}/`)  // ✅ Fetch JSON data
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        console.error("Error:", data.error);
                    } else {
                        // ✅ Populate form fields
                        document.getElementById("first-name").value = data.first_name || "";
                        document.getElementById("last-name").value = data.last_name || "";
                        document.getElementById("dob").value = data.date_of_birth || "";
                        document.getElementById("phone-number").value = data.phone_number || "";
                        document.getElementById("email").value = data.email || "";
                        document.getElementById("street-address-1").value = data.street_address_1 || "";
                        document.getElementById("street-address-2").value = data.street_address_2 || "";
                        document.getElementById("city").value = data.city || "";
                        document.getElementById("state").value = data.state || "";
                        document.getElementById("zip-code").value = data.zip_code || "";
                        document.getElementById("length-at-current-address").value = data.length_at_current_address || "";
                        document.getElementById("housing-status").value = data.housing_status || "";
                        document.getElementById("current-landlord-name").value = data.current_landlord_name || "";
                        document.getElementById("current-landlord-phone").value = data.current_landlord_phone || "";
                        document.getElementById("reason-for-moving").value = data.reason_for_moving || "";
                        document.getElementById("monthly-rent").value = data.monthly_rent || "";
                        document.getElementById("driver-license-number").value = data.driver_license_number || "";
                        document.getElementById("driver-license-state").value = data.driver_license_state || "";
                    }
                })
                .catch(error => console.error("Fetch error:", error));
        }
    });
});
