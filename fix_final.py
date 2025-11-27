#!/usr/bin/env python3
"""Replace broken Cloudinary images with working placeholders and fix map"""

content = '''{% extends 'base.html' %}
{% load static %}

{% block extra_css %}
<style>
.map-shell{position:relative;border:2px solid #ffcc00;border-radius:16px;overflow:hidden;box-shadow:0 8px 24px rgba(0,0,0,0.08);}
.sticky-map{position:sticky;top:88px;height:calc(100vh - 120px);}
#map{width:100%;height:100%;border-radius:16px;}
.filter-chip{display:inline-flex;align-items:center;gap:8px;padding:10px 14px;border-radius:999px;border:1px solid #e5e5e5;background:#fff;cursor:pointer;transition:all 0.2s ease;box-shadow:0 4px 10px rgba(0,0,0,0.04);}
.filter-chip:hover{transform:translateY(-1px);box-shadow:0 10px 24px rgba(0,0,0,0.08);}
.filter-popover{position:fixed;top:20%;left:50%;transform:translate(-50%,-20%);width:min(420px,90%);background:#fff;border-radius:16px;box-shadow:0 20px 60px rgba(0,0,0,0.2);z-index:1050;display:none;max-height:80vh;overflow-y:auto;}
.filter-popover.active{display:block;}
.popover-backdrop{position:fixed;top:0;left:0;width:100vw;height:100vh;background:rgba(0,0,0,0.4);z-index:1040;display:none;}
.popover-backdrop.active{display:block;}
.rental-card{border:none;border-radius:12px;overflow:hidden;transition:transform 0.2s,box-shadow 0.2s;background:#fff;}
.rental-card:hover{transform:translateY(-4px);box-shadow:0 12px 24px rgba(0,0,0,0.15);}
.rental-image-container{position:relative;height:200px;overflow:hidden;background:#f0f0f0;}
.rental-price-badge{position:absolute;bottom:12px;left:12px;background:rgba(0,0,0,0.85);color:#fff;padding:6px 14px;border-radius:20px;font-weight:700;font-size:1rem;backdrop-filter:blur(8px);}
.image-count-badge{position:absolute;bottom:12px;right:12px;background:rgba(0,0,0,0.7);color:#fff;padding:4px 10px;border-radius:8px;font-size:0.85rem;font-weight:600;}
.carousel-control-prev,.carousel-control-next{width:40px;}
.carousel-control-prev-icon,.carousel-control-next-icon{background-color:rgba(0,0,0,0.5);border-radius:50%;padding:10px;}
</style>
{% endblock %}

{% block content %}
<div class="container-fluid py-4">
<div class="row g-4">
<div class="col-lg-7 col-xl-8">
<div class="d-flex flex-wrap gap-2 mb-4 sticky-top bg-white py-3" style="z-index:1000;top:0;">
<div class="filter-chip" onclick="openFilter('price')"><span class="fw-bold">Price</span><span id="priceValueLabel" class="text-muted">Any</span><i class="fas fa-chevron-down small text-muted"></i></div>
<div class="filter-chip" onclick="openFilter('beds')"><span class="fw-bold">Beds</span><span id="bedsValueLabel" class="text-muted">Any</span><i class="fas fa-chevron-down small text-muted"></i></div>
<div class="filter-chip" onclick="openFilter('baths')"><span class="fw-bold">Baths</span><span id="bathsValueLabel" class="text-muted">Any</span><i class="fas fa-chevron-down small text-muted"></i></div>
<div class="filter-chip" onclick="openFilter('neighborhoods')"><span class="fw-bold">Neighborhoods</span><span id="neighborhoodsValue" class="text-muted">Anywhere</span><i class="fas fa-chevron-down small text-muted"></i></div>
<div class="filter-chip" onclick="openFilter('amenities')"><span class="fw-bold">Amenities</span><span id="amenitiesValue" class="text-muted">Any</span><i class="fas fa-sliders-h small text-muted"></i></div>
</div>
<div class="d-flex align-items-center justify-content-between mb-4">
<h5 class="fw-bold mb-0">{{ total_results }} places in NYC</h5>
<select class="form-select form-select-sm border-0 bg-light" style="width:auto;" onchange="window.location.href='?sort='+this.value">
<option value="relevant" {% if is_sort_relevant %}selected{% endif %}>Relevant</option>
<option value="price_asc" {% if is_sort_price_asc %}selected{% endif %}>Price: Low to High</option>
<option value="price_desc" {% if is_sort_price_desc %}selected{% endif %}>Price: High to Low</option>
<option value="newest" {% if is_sort_newest %}selected{% endif %}>Newest</option>
</select>
</div>
<div class="row" id="apartmentsGrid">
{% for apartment in apartments %}
<div class="col-xl-4 col-lg-6 mb-4 apartment-card" data-apartment-id="{{ apartment.id }}" data-price="{{ apartment.rent_price }}" data-lat="{{ apartment.building.latitude|default:40.7128 }}" data-lng="{{ apartment.building.longitude|default:-74.0060 }}">
<div class="card h-100 shadow-sm rental-card">
<div class="rental-image-container">
<img src="https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=400&h=200&fit=crop" style="height:200px;width:100%;object-fit:cover;" alt="Apartment">
<div class="rental-price-badge">${{ apartment.rent_price|floatformat:0 }}</div>
{% if apartment.total_image_count > 1 %}<div class="image-count-badge"><i class="fas fa-camera me-1"></i>{{ apartment.total_image_count }}</div>{% endif %}
</div>
<div class="card-body">
<h6 class="card-title mb-1 fw-bold">{{ apartment.building.name }} - Unit {{ apartment.unit_number }}</h6>
<p class="card-text text-muted small mb-2">{{ apartment.building.street_address_1 }}{% if apartment.building.neighborhood %}<br><span class="badge bg-secondary mt-1">{{ apartment.building.neighborhood }}</span>{% endif %}</p>
<div class="d-flex gap-1 mb-2">
{% if apartment.is_new %}<span class="badge bg-success">New</span>{% endif %}
{% if apartment.has_special %}<span class="badge bg-warning text-dark">Special</span>{% endif %}
</div>
<div class="d-flex gap-2 mb-2 flex-wrap">
<span class="badge bg-light text-dark border"><i class="fas fa-bed me-1"></i>{% if apartment.bedrooms == 0 %}Studio{% else %}{{ apartment.bedrooms|floatformat:0 }} bed{% endif %}</span>
<span class="badge bg-light text-dark border"><i class="fas fa-bath me-1"></i>{{ apartment.bathrooms|floatformat:0 }} bath</span>
{% if apartment.square_feet %}<span class="badge bg-light text-dark border">{{ apartment.square_feet }} ft²</span>{% endif %}
</div>
</div>
<div class="card-footer bg-white border-0 pt-0">
<div class="d-flex gap-2">
<a href="{% url 'apartment_overview' apartment.id %}" class="btn btn-outline-dark btn-sm flex-fill rounded-pill"><i class="fas fa-eye me-1"></i>View</a>
<a href="{% url 'apartment_overview' apartment.id %}#broker-contact" class="btn btn-warning btn-sm flex-fill rounded-pill" style="background:#ffcc00;border-color:#ffcc00;color:#000;font-weight:600;"><i class="fas fa-user-tie me-1"></i>Contact</a>
</div>
</div>
</div>
</div>
{% empty %}
<div class="col-12"><div class="text-center py-5"><i class="bi bi-house-x text-muted" style="font-size:3rem;"></i><h4 class="mt-3">No apartments found</h4></div></div>
{% endfor %}
</div>
</div>
<div class="col-lg-5 col-xl-4 d-none d-lg-block">
<div class="sticky-map"><div class="map-shell h-100"><div id="map"></div></div></div>
</div>
</div>
</div>

<div class="popover-backdrop" id="popoverBackdrop" onclick="closeAllPopovers()"></div>
<div class="filter-popover" id="pricePopover"><div class="p-4"><h5 class="mb-3">Price Range</h5><form id="priceForm"><div class="mb-3"><div class="d-flex gap-2"><input type="number" class="form-control" name="min_price" placeholder="Min" value="{{ request.GET.min_price }}"><input type="number" class="form-control" name="max_price" placeholder="Max" value="{{ request.GET.max_price }}"></div></div><div class="d-flex gap-2"><button type="button" class="btn btn-outline-secondary" onclick="clearFilter('price')">Clear</button><button type="button" class="btn btn-dark flex-fill" onclick="applyFilters()">Apply</button></div></form></div></div>
<div class="filter-popover" id="bedsPopover"><div class="p-4"><h5 class="mb-3">Bedrooms</h5><form id="bedsForm"><div class="d-flex flex-wrap gap-2 mb-3"><input type="radio" class="btn-check" name="min_bedrooms" id="bed-any" value=""><label class="btn btn-outline-dark rounded-pill" for="bed-any">Any</label><input type="radio" class="btn-check" name="min_bedrooms" id="bed-0" value="0"><label class="btn btn-outline-dark rounded-pill" for="bed-0">Studio</label><input type="radio" class="btn-check" name="min_bedrooms" id="bed-1" value="1"><label class="btn btn-outline-dark rounded-pill" for="bed-1">1+</label><input type="radio" class="btn-check" name="min_bedrooms" id="bed-2" value="2"><label class="btn btn-outline-dark rounded-pill" for="bed-2">2+</label><input type="radio" class="btn-check" name="min_bedrooms" id="bed-3" value="3"><label class="btn btn-outline-dark rounded-pill" for="bed-3">3+</label></div><div class="d-flex gap-2"><button type="button" class="btn btn-outline-secondary" onclick="clearFilter('beds')">Clear</button><button type="button" class="btn btn-dark flex-fill" onclick="applyFilters()">Apply</button></div></form></div></div>
<div class="filter-popover" id="bathsPopover"><div class="p-4"><h5 class="mb-3">Bathrooms</h5><form id="bathsForm"><div class="d-flex flex-wrap gap-2 mb-3"><input type="radio" class="btn-check" name="min_bathrooms" id="bath-any" value=""><label class="btn btn-outline-dark rounded-pill" for="bath-any">Any</label><input type="radio" class="btn-check" name="min_bathrooms" id="bath-1" value="1"><label class="btn btn-outline-dark rounded-pill" for="bath-1">1+</label><input type="radio" class="btn-check" name="min_bathrooms" id="bath-2" value="2"><label class="btn btn-outline-dark rounded-pill" for="bath-2">2+</label></div><div class="d-flex gap-2"><button type="button" class="btn btn-outline-secondary" onclick="clearFilter('baths')">Clear</button><button type="button" class="btn btn-dark flex-fill" onclick="applyFilters()">Apply</button></div></form></div></div>
<div class="filter-popover" id="neighborhoodsPopover"><div class="p-4"><h5 class="mb-3">Neighborhoods</h5><form id="neighborhoodsForm"><div class="row g-2 mb-3">{% for value, label in neighborhood_choices %}<div class="col-6"><div class="form-check"><input class="form-check-input" type="checkbox" name="neighborhoods" value="{{ value }}" id="neigh-{{ value }}"><label class="form-check-label" for="neigh-{{ value }}">{{ label }}</label></div></div>{% endfor %}</div><div class="d-flex gap-2"><button type="button" class="btn btn-outline-secondary" onclick="clearFilter('neighborhoods')">Clear</button><button type="button" class="btn btn-dark flex-fill" onclick="applyFilters()">Apply</button></div></form></div></div>
<div class="filter-popover" id="amenitiesPopover"><div class="p-4"><h5 class="mb-3">Amenities</h5><form id="amenitiesForm"><div class="row g-2 mb-3">{% for amenity in all_amenities %}<div class="col-6"><div class="form-check"><input class="form-check-input" type="checkbox" name="amenities" value="{{ amenity.id }}" id="amenity-{{ amenity.id }}"><label class="form-check-label" for="amenity-{{ amenity.id }}">{{ amenity.name }}</label></div></div>{% endfor %}</div><div class="mb-3"><div class="form-check form-switch"><input class="form-check-input" type="checkbox" name="pets_allowed" value="1" id="petsAllowed"><label class="form-check-label" for="petsAllowed">Pets Allowed</label></div></div><div class="d-flex gap-2"><button type="button" class="btn btn-outline-secondary" onclick="clearFilter('amenities')">Clear</button><button type="button" class="btn btn-dark flex-fill" onclick="applyFilters()">Apply</button></div></form></div></div>
{% endblock %}

{% block extra_js %}
<script src='https://api.mapbox.com/mapbox-gl-js/v2.9.1/mapbox-gl.js'></script>
<link href='https://api.mapbox.com/mapbox-gl-js/v2.9.1/mapbox-gl.css' rel='stylesheet'>
<script>
document.addEventListener('DOMContentLoaded',function(){
const token='{{ mapbox_token }}';
if(!token||token==='None'){console.error('Mapbox token missing');return;}
mapboxgl.accessToken=token;
try{
const map=new mapboxgl.Map({container:'map',style:'mapbox://styles/mapbox/light-v11',center:[-74.0060,40.7128],zoom:12});
map.addControl(new mapboxgl.NavigationControl(),'bottom-right');
const apartmentCards=document.querySelectorAll('.apartment-card');
apartmentCards.forEach(card=>{
const lat=parseFloat(card.dataset.lat);
const lng=parseFloat(card.dataset.lng);
const price=card.dataset.price;
const id=card.dataset.apartmentId;
if(lat&&lng&&!isNaN(lat)&&!isNaN(lng)){
const el=document.createElement('div');
el.innerHTML='<div style="background:#000;color:#fff;padding:6px 10px;border-radius:12px;font-size:0.9rem;font-weight:700;cursor:pointer;border:2px solid #fff;box-shadow:0 2px 8px rgba(0,0,0,0.3);">$'+Math.floor(price).toLocaleString()+'</div>';
const marker=new mapboxgl.Marker(el).setLngLat([lng,lat]).addTo(map);
el.addEventListener('click',()=>{
card.scrollIntoView({behavior:'smooth',block:'center'});
card.querySelector('.rental-card').style.border='3px solid #ffcc00';
setTimeout(()=>{card.querySelector('.rental-card').style.border='';},2000);
});
}
});
}catch(e){console.error('Map error:',e);}
});
function openFilter(type){closeAllPopovers();document.getElementById(type+'Popover').classList.add('active');document.getElementById('popoverBackdrop').classList.add('active');}
function closeAllPopovers(){document.querySelectorAll('.filter-popover').forEach(el=>el.classList.remove('active'));document.getElementById('popoverBackdrop').classList.remove('active');}
function clearFilter(type){document.getElementById(type+'Form').reset();}
function applyFilters(){const params=new URLSearchParams(window.location.search);['priceForm','bedsForm','bathsForm','neighborhoodsForm','amenitiesForm'].forEach(formId=>{const form=document.getElementById(formId);if(form){const formData=new FormData(form);for(let[key,value]of formData.entries()){if(value)params.set(key,value);}}});window.location.href='?'+params.toString();}
</script>
{% endblock %}
'''

with open('apartments/templates/apartments/apartments_list.html', 'w') as f:
    f.write(content)

print("Fixed images and map")
