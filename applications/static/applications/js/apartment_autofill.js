document.addEventListener("DOMContentLoaded", function () {
    const apartmentSelect = document.getElementById("apartment-select");  // ✅ Fix here

    apartmentSelect.addEventListener("change", function () {
        const apartmentId = this.value;
        if (apartmentId) {
            fetch(`/apartments/get-apartment-data/${apartmentId}/`)  // ✅ Fetch JSON data
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        console.error("Error:", data.error);
                    } else {
                        // ✅ Populate form fields (if needed)
                        document.getElementById("rent-price").value = data.rent_price || "";
                        document.getElementById("bedrooms").value = data.bedrooms || "";
                        document.getElementById("bathrooms").value = data.bathrooms || "";
                        document.getElementById("square-feet").value = data.square_feet || "";
                    }
                })
                .catch(error => console.error("Fetch error:", error));
        }
    });
});
