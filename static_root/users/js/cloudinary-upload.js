document.addEventListener('DOMContentLoaded', function() {
    // Initialize all Cloudinary upload fields
    const uploadFields = document.querySelectorAll('[data-cloudinary-field="true"]');
    
    uploadFields.forEach(field => {
        initializePhotoUpload(field);
    });
    
    function initializePhotoUpload(field) {
        const fieldId = field.id;
        const container = document.getElementById(`photo-upload-${fieldId}`);
        const uploadBtn = document.getElementById(`upload-btn-${fieldId}`);
        const deleteBtn = document.getElementById(`delete-btn-${fieldId}`);
        const progressDiv = document.getElementById(`upload-progress-${fieldId}`);
        const progressBar = document.getElementById(`progress-bar-${fieldId}`);
        const currentPhoto = document.getElementById(`current-photo-${fieldId}`);
        const placeholder = document.getElementById(`photo-placeholder-${fieldId}`);
        
        // Get Cloudinary options from data attribute
        let cloudinaryOptions = {};
        try {
            cloudinaryOptions = JSON.parse(field.dataset.cloudinaryOptions || '{}');
            console.log('Parsed cloudinary options:', cloudinaryOptions);
        } catch (e) {
            console.error('Invalid Cloudinary options:', e);
        }
        
        // Set up Cloudinary configuration for unsigned uploads
        const cloudName = cloudinaryOptions.cloud_name || window.CLOUDINARY_CLOUD_NAME;
        const uploadPreset = 'unsigned_cards';  // Use the whitelisted unsigned preset
        
        // Initialize Cloudinary Upload Widget
        if (uploadBtn) {
            uploadBtn.addEventListener('click', function() {
                console.log('Initializing Cloudinary widget with:', {
                    cloudName: cloudName,
                    uploadPreset: uploadPreset
                });
                
                // Merge options from widget with defaults - minimal clean interface
                const widgetConfig = {
                    cloudName: cloudName,
                    uploadPreset: uploadPreset,
                    sources: ['local'],  // Only allow local file uploads
                    multiple: false,
                    maxFiles: 1,
                    cropping: false,  // Disable cropping for cleaner interface
                    showAdvancedOptions: false,  // Hide advanced settings
                    showSkipCropButton: false,  // Simplify interface
                    showCompletedButton: true,  // Only show completion state
                    showUploadMoreButton: false,  // Prevent additional uploads
                    showPoweredBy: false,  // Remove Cloudinary branding
                    folder: 'admin_profiles',
                    resourceType: 'image',
                    clientAllowedFormats: ['jpg', 'jpeg', 'png', 'gif', 'webp'],
                    maxFileSize: 10485760, // 10MB
                    thumbnailTransformation: [
                        { width: 200, height: 200, crop: 'fill', gravity: 'face' }
                    ],
                    // Override with any options from widget
                    ...cloudinaryOptions
                };
                
                console.log('Final widget config:', widgetConfig);
                
                // Add styles to widget config
                widgetConfig.styles = {
                        palette: {
                            window: '#FFFFFF',
                            windowBorder: '#90A0B3',
                            tabIcon: '#ffcc00',
                            menuIcons: '#5A616A',
                            textDark: '#000000',
                            textLight: '#FFFFFF',
                            link: '#ffcc00',
                            action: '#ffcc00',
                            inactiveTabIcon: '#0E2F5A',
                            error: '#F44235',
                            inProgress: '#ffcc00',
                            complete: '#20B832',
                            sourceBg: '#E4EBF1'
                        },
                        fonts: {
                            default: null,
                            "'Fira Sans', sans-serif": {
                                url: 'https://fonts.googleapis.com/css?family=Fira+Sans',
                                active: true
                            }
                        }
                    };
                
                const widget = cloudinary.createUploadWidget(widgetConfig, (error, result) => {
                    if (!error && result && result.event === 'success') {
                        // Update the hidden field with the public_id
                        field.value = result.info.public_id;
                        
                        // Update the preview
                        updatePhotoPreview(result.info);
                        
                        // Show success message
                        showNotification('Photo uploaded successfully!', 'success');
                    } else if (error) {
                        console.error('Upload error:', error);
                        showNotification('Upload failed. Please try again.', 'danger');
                    }
                });
                
                widget.open();
            });
        }
        
        // Delete photo functionality
        if (deleteBtn) {
            deleteBtn.addEventListener('click', function() {
                if (confirm('Are you sure you want to remove your profile photo?')) {
                    // Clear the field value
                    field.value = '';
                    field.dataset.publicId = '';
                    field.dataset.currentPhoto = '';
                    
                    // Update UI
                    if (currentPhoto) {
                        currentPhoto.remove();
                    }
                    
                    // Show placeholder
                    const wrapper = container.querySelector('.current-photo-wrapper');
                    if (wrapper && !wrapper.querySelector('.photo-placeholder')) {
                        wrapper.innerHTML = `
                            <div class="photo-placeholder" id="photo-placeholder-${fieldId}">
                                <i class="fas fa-user-circle"></i>
                                <span>No photo uploaded</span>
                            </div>
                        `;
                    }
                    
                    // Update button text
                    if (uploadBtn) {
                        uploadBtn.innerHTML = '<i class="fas fa-camera"></i> Upload Photo';
                    }
                    
                    // Hide delete and zoom buttons
                    deleteBtn.style.display = 'none';
                    const zoomBtns = container.querySelectorAll('.zoom-in-btn, .zoom-out-btn');
                    zoomBtns.forEach(btn => btn.style.display = 'none');
                    
                    showNotification('Photo removed successfully', 'info');
                }
            });
        }
        
        // Zoom functionality
        const zoomInBtn = container.querySelector('.zoom-in-btn');
        const zoomOutBtn = container.querySelector('.zoom-out-btn');
        
        if (zoomInBtn && currentPhoto) {
            let currentZoom = 1;
            
            zoomInBtn.addEventListener('click', function() {
                currentZoom = Math.min(currentZoom + 0.2, 3);
                currentPhoto.style.transform = `scale(${currentZoom})`;
            });
            
            if (zoomOutBtn) {
                zoomOutBtn.addEventListener('click', function() {
                    currentZoom = Math.max(currentZoom - 0.2, 1);
                    currentPhoto.style.transform = `scale(${currentZoom})`;
                });
            }
        }
        
        function updatePhotoPreview(photoInfo) {
            const wrapper = container.querySelector('.current-photo-wrapper');
            
            // Create optimized URL with transformations
            const photoUrl = `https://res.cloudinary.com/${cloudName}/image/upload/w_200,h_200,c_fill,g_face,q_auto,f_auto/${photoInfo.public_id}`;
            
            // Update or create image element
            let img = document.getElementById(`current-photo-${fieldId}`);
            if (!img) {
                // Remove placeholder if exists
                const placeholder = wrapper.querySelector('.photo-placeholder');
                if (placeholder) {
                    placeholder.remove();
                }
                
                img = document.createElement('img');
                img.id = `current-photo-${fieldId}`;
                img.className = 'current-photo';
                img.alt = 'Current profile photo';
                wrapper.appendChild(img);
            }
            
            img.src = photoUrl;
            
            // Update field data
            field.dataset.currentPhoto = photoUrl;
            field.dataset.publicId = photoInfo.public_id;
            
            // Update buttons
            if (uploadBtn) {
                uploadBtn.innerHTML = '<i class="fas fa-camera"></i> Change Photo';
            }
            
            // Show delete and zoom buttons
            if (deleteBtn) {
                deleteBtn.style.display = 'inline-block';
            }
            
            const zoomBtns = container.querySelectorAll('.zoom-in-btn, .zoom-out-btn');
            zoomBtns.forEach(btn => btn.style.display = 'inline-block');
        }
    }
    
    function showNotification(message, type) {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
        notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 250px;';
        notification.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        document.body.appendChild(notification);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            notification.remove();
        }, 5000);
    }
});

// Global function to handle Cloudinary widget callbacks
window.handleCloudinaryUpload = function(error, result, fieldId) {
    if (!error && result && result.event === 'success') {
        // Trigger a custom event that can be handled by form submit
        const event = new CustomEvent('cloudinaryUploadSuccess', {
            detail: {
                fieldId: fieldId,
                publicId: result.info.public_id,
                url: result.info.secure_url,
                info: result.info
            }
        });
        document.dispatchEvent(event);
    }
};