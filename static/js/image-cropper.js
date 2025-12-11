/**
 * Universal Image Cropper Component
 * Provides professional image cropping functionality for any file input
 * Uses Cropper.js for the interface
 */

class UniversalImageCropper {
    constructor(options = {}) {
        this.options = {
            aspectRatio: options.aspectRatio || 1, // Default square
            viewMode: options.viewMode || 2,
            dragMode: options.dragMode || 'move',
            autoCropArea: options.autoCropArea || 0.8,
            outputWidth: options.outputWidth || 400,
            outputHeight: options.outputHeight || 400,
            outputQuality: options.outputQuality || 0.9,
            preview: options.preview || null, // CSS selector for preview element
            maxFileSize: options.maxFileSize || 10 * 1024 * 1024, // 10MB
            allowedTypes: options.allowedTypes || ['image/jpeg', 'image/png', 'image/gif', 'image/webp'],
            cropButtonText: options.cropButtonText || 'Crop & Zoom',
            previewButtonText: options.previewButtonText || 'View Full Size',
            modalTitle: options.modalTitle || 'Crop Your Image',
            showPreviewButton: options.showPreviewButton !== false,
            showCropButton: options.showCropButton !== false,
            showDeleteButton: options.showDeleteButton !== false,
            onCrop: options.onCrop || null,
            onDelete: options.onDelete || null,
            onUpload: options.onUpload || null,
            ...options
        };
        
        this.cropper = null;
        this.currentImageSrc = null;
        this.fileInput = null;
        this.previewElement = null;
        this.cropDataInput = null;
        
        this.init();
    }
    
    init() {
        this.createModal();
        this.attachStyles();
    }
    
    attachToFileInput(inputSelector, previewSelector = null, cropDataSelector = null) {
        this.fileInput = document.querySelector(inputSelector);
        this.previewElement = previewSelector ? document.querySelector(previewSelector) : null;
        this.cropDataInput = cropDataSelector ? document.querySelector(cropDataSelector) : null;
        
        if (!this.fileInput) {
            console.warn('UniversalImageCropper: File input not found:', inputSelector);
            return;
        }
        
        this.setupFileInputHandler();
        this.createButtons();
        
        return this;
    }
    
    setupFileInputHandler() {
        this.fileInput.addEventListener('change', (event) => {
            const file = event.target.files[0];
            if (file) {
                if (this.validateFile(file)) {
                    this.loadImage(file);
                }
            }
        });
    }
    
    loadExistingImage(imageUrl) {
        // Load an existing image URL into the cropper
        this.currentImageSrc = imageUrl;
        this.updateButtons(true);
        
        // Update the preview if it exists
        if (this.previewElement) {
            this.updatePreview(imageUrl);
        }
        
        if (this.options.onUpload) {
            this.options.onUpload(null, imageUrl);
        }
    }
    
    validateFile(file) {
        if (!this.options.allowedTypes.includes(file.type)) {
            this.showToast(`Please select a valid image file (${this.options.allowedTypes.join(', ')}).`, 'error');
            this.fileInput.value = '';
            return false;
        }
        
        if (file.size > this.options.maxFileSize) {
            this.showToast(`File size must be less than ${Math.round(this.options.maxFileSize / (1024 * 1024))}MB.`, 'error');
            this.fileInput.value = '';
            return false;
        }
        
        return true;
    }
    
    loadImage(file) {
        const reader = new FileReader();
        reader.onload = (e) => {
            this.currentImageSrc = e.target.result;
            this.updatePreview(this.currentImageSrc);
            this.updateButtons(true);
            this.showToast('Image uploaded! Click "' + this.options.cropButtonText + '" to adjust.', 'success');
            
            if (this.options.onUpload) {
                this.options.onUpload(file, this.currentImageSrc);
            }
        };
        reader.readAsDataURL(file);
    }
    
    updatePreview(imageSrc) {
        if (!this.previewElement) return;
        
        // Find placeholder and existing image
        const placeholder = this.previewElement.querySelector('.image-placeholder');
        const existingImg = this.previewElement.querySelector('.preview-image');
        
        // Hide placeholder
        if (placeholder) {
            placeholder.style.display = 'none';
        }
        
        if (existingImg) {
            // Update existing image
            existingImg.src = imageSrc;
            existingImg.style.display = 'block';
            
            // Update size for existing images
            if (this.options.isPetPhoto) {
                existingImg.style.width = '160px';
                existingImg.style.height = '120px';
                existingImg.style.borderRadius = '4px';
            } else if (this.options.isDocument) {
                existingImg.style.width = '200px';
                existingImg.style.height = '125px';
                existingImg.style.borderRadius = '4px';
            }
        } else {
            // Create new image element  
            const img = document.createElement('img');
            img.className = 'preview-image';
            img.src = imageSrc;
            
            // Apply styling based on image type
            let styling = 'object-fit: cover; cursor: pointer; border: 2px solid #ffcc00; position: absolute; top: 0; left: 0;';
            if (this.options.isPetPhoto) {
                // Rectangular styling for pet photos
                styling += ` width: 160px; height: 120px; border-radius: 4px;`;
            } else if (this.options.isDocument) {
                // Rectangular styling for documents - much bigger
                styling += ` width: 200px; height: 125px; border-radius: 4px;`;
            } else {
                // Circular styling for profile photos
                styling += ` width: 120px; height: 120px; border-radius: 50%;`;
            }
            
            img.style.cssText = styling;
            img.onclick = () => this.showCropper();
            this.previewElement.appendChild(img);
        }
    }
    
    createButtons() {
        const container = this.fileInput.parentNode;
        
        // Create button container
        let buttonContainer = container.querySelector('.image-cropper-buttons');
        if (!buttonContainer) {
            buttonContainer = document.createElement('div');
            buttonContainer.className = 'image-cropper-buttons d-flex gap-2 mt-2';
            container.appendChild(buttonContainer);
        }
        
        // Check if buttons already exist to prevent duplicates
        if (buttonContainer.querySelector('.btn[data-cropper-button]')) {
            return; // Buttons already created, don't create duplicates
        }
        
        // Crop button
        if (this.options.showCropButton) {
            const cropBtn = document.createElement('button');
            cropBtn.type = 'button';
            cropBtn.className = 'btn btn-outline-warning btn-sm';
            cropBtn.setAttribute('data-cropper-button', 'crop');
            cropBtn.innerHTML = `<i class="fas fa-crop"></i> ${this.options.cropButtonText}`;
            cropBtn.style.display = 'none';
            cropBtn.onclick = () => this.showCropper();
            cropBtn.id = `crop-btn-${Math.random().toString(36).substr(2, 9)}`;
            this.cropButton = cropBtn;
            buttonContainer.appendChild(cropBtn);
        }
        
        // Preview button
        if (this.options.showPreviewButton) {
            const previewBtn = document.createElement('button');
            previewBtn.type = 'button';
            previewBtn.className = 'btn btn-outline-secondary btn-sm';
            previewBtn.setAttribute('data-cropper-button', 'preview');
            previewBtn.innerHTML = `<i class="fas fa-eye"></i> ${this.options.previewButtonText}`;
            previewBtn.style.display = 'none';
            previewBtn.onclick = () => this.showFullPreview();
            this.previewButton = previewBtn;
            buttonContainer.appendChild(previewBtn);
        }
        
        // Delete button
        if (this.options.showDeleteButton) {
            const deleteBtn = document.createElement('button');
            deleteBtn.type = 'button';
            deleteBtn.className = 'btn btn-outline-danger btn-sm';
            deleteBtn.setAttribute('data-cropper-button', 'delete');
            deleteBtn.innerHTML = '<i class="fas fa-trash"></i> Remove';
            deleteBtn.style.display = 'none';
            deleteBtn.onclick = () => this.removeImage();
            this.deleteButton = deleteBtn;
            buttonContainer.appendChild(deleteBtn);
        }
    }
    
    updateButtons(show = false) {
        if (this.cropButton) this.cropButton.style.display = show ? 'inline-block' : 'none';
        if (this.previewButton) this.previewButton.style.display = show ? 'inline-block' : 'none';
        if (this.deleteButton) this.deleteButton.style.display = show ? 'inline-block' : 'none';
    }
    
    removeImage() {
        if (confirm('Are you sure you want to remove this image?')) {
            this.fileInput.value = '';
            this.currentImageSrc = null;
            
            if (this.cropDataInput) {
                this.cropDataInput.value = '';
            }
            
            // Reset preview
            if (this.previewElement) {
                const placeholder = this.previewElement.querySelector('.image-placeholder');
                const existingImg = this.previewElement.querySelector('.preview-image');
                
                if (placeholder) placeholder.style.display = 'block';
                if (existingImg) existingImg.style.display = 'none';
            }
            
            this.updateButtons(false);
            
            if (this.options.onDelete) {
                this.options.onDelete();
            }
        }
    }
    
    showCropper() {
        if (!this.currentImageSrc) {
            this.showToast('Please upload an image first.', 'error');
            return;
        }
        
        // Set current instance reference for modal buttons
        window.currentImageCropperInstance = this;
        
        const cropImage = document.getElementById('universal-crop-image');
        cropImage.src = this.currentImageSrc;
        
        const modal = new bootstrap.Modal(document.getElementById('universal-cropper-modal'));
        modal.show();
        
        // Initialize cropper after modal is shown
        document.getElementById('universal-cropper-modal').addEventListener('shown.bs.modal', () => {
            this.initializeCropper();
        }, { once: true });
        
        // Clean up cropper when modal is hidden
        document.getElementById('universal-cropper-modal').addEventListener('hidden.bs.modal', () => {
            this.destroyCropper();
        });
    }
    
    initializeCropper() {
        if (this.cropper) {
            this.cropper.destroy();
        }
        
        const cropImage = document.getElementById('universal-crop-image');
        this.cropper = new Cropper(cropImage, {
            aspectRatio: this.options.aspectRatio,
            viewMode: this.options.viewMode,
            dragMode: this.options.dragMode,
            autoCropArea: this.options.autoCropArea,
            responsive: true,
            restore: false,
            guides: true,
            center: true,
            highlight: false,
            cropBoxMovable: true,
            cropBoxResizable: true,
            toggleDragModeOnDblclick: false,
            minContainerWidth: 400,
            minContainerHeight: 300,
            ready: () => {
                // Apply circular styling for profile photos only
                const viewBox = document.querySelector('.cropper-view-box');
                const face = document.querySelector('.cropper-face');
                
                if (viewBox && face) {
                    if (!this.options.isDocument && !this.options.isPetPhoto && this.options.aspectRatio === 1) {
                        // Profile photos only: circular
                        viewBox.classList.add('circular');
                        face.classList.add('circular');
                    } else {
                        // Documents and pet photos: rectangular (remove circular if it was there)
                        viewBox.classList.remove('circular');
                        face.classList.remove('circular');
                    }
                }
            }
        });
    }
    
    destroyCropper() {
        if (this.cropper) {
            this.cropper.destroy();
            this.cropper = null;
        }
    }
    
    applyCrop() {
        if (!this.cropper) return;
        
        const canvas = this.cropper.getCroppedCanvas({
            width: this.options.outputWidth,
            height: this.options.outputHeight,
            fillColor: '#fff',
            imageSmoothingEnabled: true,
            imageSmoothingQuality: 'high'
        });
        
        if (canvas) {
            canvas.toBlob((blob) => {
                const croppedDataUrl = canvas.toDataURL('image/jpeg', this.options.outputQuality);
                
                // Update preview
                this.updatePreview(croppedDataUrl);
                
                // Store crop data
                if (this.cropDataInput) {
                    const cropData = this.cropper.getData();
                    this.cropDataInput.value = JSON.stringify({
                        cropped: true,
                        data: cropData,
                        croppedImage: croppedDataUrl
                    });
                }
                
                // Close modal
                const modal = bootstrap.Modal.getInstance(document.getElementById('universal-cropper-modal'));
                modal.hide();
                
                this.showToast('Image cropped successfully!', 'success');
                
                if (this.options.onCrop) {
                    this.options.onCrop(croppedDataUrl, blob);
                }
            }, 'image/jpeg', this.options.outputQuality);
        }
    }
    
    showFullPreview() {
        if (!this.currentImageSrc) return;
        
        const modalPhoto = document.getElementById('universal-preview-image');
        modalPhoto.src = this.currentImageSrc;
        
        const modal = new bootstrap.Modal(document.getElementById('universal-preview-modal'));
        modal.show();
    }
    
    createModal() {
        // Check if modals already exist
        if (document.getElementById('universal-cropper-modal')) {
            // Modal exists, just make sure we have current instance reference
            window.currentImageCropperInstance = this;
            return;
        }
        
        const modalHTML = `
        <!-- Universal Cropper Modal -->
        <div class="modal fade" id="universal-cropper-modal" tabindex="-1">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">
                            <i class="fas fa-crop"></i> ${this.options.modalTitle}
                        </h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="img-container">
                            <img id="universal-crop-image" style="max-width: 100%; display: block;">
                        </div>
                        <div class="mt-3">
                            <div class="btn-group" role="group">
                                <button type="button" class="btn btn-outline-primary btn-sm" id="universal-zoom-in">
                                    <i class="fas fa-search-plus"></i> Zoom In
                                </button>
                                <button type="button" class="btn btn-outline-primary btn-sm" id="universal-zoom-out">
                                    <i class="fas fa-search-minus"></i> Zoom Out
                                </button>
                                <button type="button" class="btn btn-outline-primary btn-sm" id="universal-rotate-left">
                                    <i class="fas fa-undo"></i> Rotate Left
                                </button>
                                <button type="button" class="btn btn-outline-primary btn-sm" id="universal-rotate-right">
                                    <i class="fas fa-redo"></i> Rotate Right
                                </button>
                                <button type="button" class="btn btn-outline-secondary btn-sm" id="universal-reset-crop">
                                    <i class="fas fa-refresh"></i> Reset
                                </button>
                            </div>
                        </div>
                        <div class="mt-3">
                            <small class="text-muted">
                                <i class="fas fa-info-circle"></i> 
                                Drag to move, use corners to resize, scroll to zoom.
                            </small>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                            <i class="fas fa-times"></i> Cancel
                        </button>
                        <button type="button" class="btn btn-primary" id="universal-apply-crop">
                            <i class="fas fa-check"></i> Apply Crop
                        </button>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Universal Preview Modal -->
        <div class="modal fade" id="universal-preview-modal" tabindex="-1">
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Image Preview</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body text-center">
                        <img id="universal-preview-image" class="img-fluid rounded">
                    </div>
                </div>
            </div>
        </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', modalHTML);
        
        // Set global instance reference for modal event handlers
        window.currentImageCropperInstance = this;
        
        // Attach event listeners
        this.attachModalEventListeners();
    }
    
    attachModalEventListeners() {
        // Only attach listeners once
        if (window.universalCropperListenersAttached) return;
        
        document.getElementById('universal-zoom-in').addEventListener('click', () => {
            const instance = window.currentImageCropperInstance;
            if (instance && instance.cropper) instance.cropper.zoom(0.1);
        });
        
        document.getElementById('universal-zoom-out').addEventListener('click', () => {
            const instance = window.currentImageCropperInstance;
            if (instance && instance.cropper) instance.cropper.zoom(-0.1);
        });
        
        document.getElementById('universal-rotate-left').addEventListener('click', () => {
            const instance = window.currentImageCropperInstance;
            if (instance && instance.cropper) instance.cropper.rotate(-90);
        });
        
        document.getElementById('universal-rotate-right').addEventListener('click', () => {
            const instance = window.currentImageCropperInstance;
            if (instance && instance.cropper) instance.cropper.rotate(90);
        });
        
        document.getElementById('universal-reset-crop').addEventListener('click', () => {
            const instance = window.currentImageCropperInstance;
            if (instance && instance.cropper) instance.cropper.reset();
        });
        
        document.getElementById('universal-apply-crop').addEventListener('click', () => {
            const instance = window.currentImageCropperInstance;
            if (instance) instance.applyCrop();
        });
        
        // Mark listeners as attached
        window.universalCropperListenersAttached = true;
    }
    
    attachStyles() {
        if (document.getElementById('universal-cropper-styles')) return;
        
        const styleSheet = document.createElement('style');
        styleSheet.id = 'universal-cropper-styles';
        styleSheet.textContent = `
            .img-container {
                max-height: 400px;
                overflow: hidden;
            }
            
            .img-container img {
                max-width: 100%;
                height: auto;
            }
            
            .cropper-view-box,
            .cropper-face {
                border-radius: 8px; /* Default rectangular */
            }
            
            .cropper-view-box.circular,
            .cropper-face.circular {
                border-radius: 50%;
            }
            
            .cropper-view-box {
                box-shadow: 0 0 0 1px #39f;
                outline: 0;
            }
            
            .image-cropper-buttons {
                margin-top: 0.5rem;
            }
            
            .preview-image {
                transition: all 0.3s ease;
            }
            
            .preview-image:hover {
                transform: scale(1.05);
            }
        `;
        
        document.head.appendChild(styleSheet);
    }
    
    showToast(message, type = 'info') {
        const alertClass = type === 'error' ? 'alert-danger' : type === 'success' ? 'alert-success' : 'alert-info';
        const iconClass = type === 'error' ? 'fa-exclamation-triangle' : type === 'success' ? 'fa-check-circle' : 'fa-info-circle';
        
        const toast = document.createElement('div');
        toast.className = `alert ${alertClass} alert-dismissible fade show position-fixed`;
        toast.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px; max-width: 400px;';
        toast.innerHTML = `
            <i class="fas ${iconClass} me-2"></i>${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        document.body.appendChild(toast);
        
        setTimeout(() => {
            if (toast.parentNode) {
                toast.remove();
            }
        }, 5000);
    }
}

// Global instance for easy access
window.UniversalImageCropper = UniversalImageCropper;

// Helper function for quick setup
window.setupImageCropper = function(inputSelector, previewSelector = null, cropDataSelector = null, options = {}) {
    const cropper = new UniversalImageCropper(options);
    return cropper.attachToFileInput(inputSelector, previewSelector, cropDataSelector);
};
