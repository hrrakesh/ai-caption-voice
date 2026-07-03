document.addEventListener('DOMContentLoaded', () => {
    // === Theme Toggle Logic ===
    const themeToggleBtn = document.getElementById('theme-toggle');
    
    // Set initial icon based on active theme
    if (themeToggleBtn) {
        updateThemeToggleIcon();
        themeToggleBtn.addEventListener('click', () => {
            const isLight = document.documentElement.classList.toggle('light-theme');
            localStorage.setItem('theme', isLight ? 'light' : 'dark');
            updateThemeToggleIcon();
        });
    }

    function updateThemeToggleIcon() {
        const icon = themeToggleBtn.querySelector('i');
        if (document.documentElement.classList.contains('light-theme')) {
            icon.className = 'fa-solid fa-sun';
            themeToggleBtn.title = 'Switch to Dark Theme';
        } else {
            icon.className = 'fa-solid fa-moon';
            themeToggleBtn.title = 'Switch to Light Theme';
        }
    }

    // === Alert Dismissal Logic (Auto-dismiss toasts) ===
    const alertContainer = document.getElementById('global-alert-container');
    if (alertContainer) {
        const alerts = alertContainer.querySelectorAll('.glass-alert');
        alerts.forEach(alert => {
            setupAlertDismissal(alert);
        });
    }

    function setupAlertDismissal(alert) {
        // Auto dismiss after 4.5 seconds
        setTimeout(() => {
            alert.classList.add('fade-out');
            setTimeout(() => {
                alert.remove();
            }, 350);
        }, 4500);
    }

    // Helper to create toasts dynamically
    function showToast(message, type = 'info') {
        const container = document.getElementById('global-alert-container');
        if (!container) return;

        const toast = document.createElement('div');
        toast.className = `glass-alert alert-${type}`;
        
        let iconClass = 'fa-circle-info';
        if (type === 'success') iconClass = 'fa-circle-check';
        if (type === 'danger') iconClass = 'fa-circle-exclamation';

        toast.innerHTML = `
            <i class="fa-solid ${iconClass} alert-icon"></i>
            <span class="alert-text">${message}</span>
            <button class="alert-close-btn" onclick="this.parentElement.remove();">&times;</button>
        `;

        container.appendChild(toast);
        setupAlertDismissal(toast);
    }

    // === File Upload and Magic Generation ===
    const dropzone = document.getElementById('dropzone');
    const imageInput = document.getElementById('image-input');
    const dropzoneContent = document.getElementById('dropzone-content');
    const previewContainer = document.getElementById('preview-container');
    const imagePreview = document.getElementById('image-preview');
    const removeImgBtn = document.getElementById('remove-img-btn');
    const uploadForm = document.getElementById('upload-form');
    const submitBtn = document.getElementById('submit-btn');
    
    const resultCard = document.getElementById('result-card');
    const resultImage = document.getElementById('result-image');
    const resultCaption = document.getElementById('result-caption');
    const resultAudio = document.getElementById('result-audio');
    const downloadAudioBtn = document.getElementById('download-audio-btn');
    const copyBtn = document.getElementById('copy-btn');
    
    const loadingOverlay = document.getElementById('loading-overlay');
    const loadingStep = document.getElementById('loading-step');
    const historyGrid = document.getElementById('history-grid');
    const noHistoryMsg = document.getElementById('no-history-msg');

    // Drag & Drop handlers
    if (dropzone) {
        ['dragenter', 'dragover'].forEach(eventName => {
            dropzone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropzone.classList.add('drag-active');
            }, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropzone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropzone.classList.remove('drag-active');
            }, false);
        });

        dropzone.addEventListener('drop', (e) => {
            const dt = e.dataTransfer;
            const files = dt.files;
            if (files.length > 0) {
                imageInput.files = files;
                handleImageSelect(files[0]);
            }
        });

        imageInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                handleImageSelect(e.target.files[0]);
            }
        });
    }

    function handleImageSelect(file) {
        if (!file.type.startsWith('image/')) {
            showToast('Please select a valid image file.', 'danger');
            return;
        }

        const reader = new FileReader();
        reader.onload = (e) => {
            imagePreview.src = e.target.result;
            dropzoneContent.classList.add('hidden');
            previewContainer.classList.remove('hidden');
        };
        reader.readAsDataURL(file);
    }

    if (removeImgBtn) {
        removeImgBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            imageInput.value = '';
            imagePreview.src = '#';
            previewContainer.classList.add('hidden');
            dropzoneContent.classList.remove('hidden');
        });
    }

    // Form Submission
    if (uploadForm) {
        uploadForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const file = imageInput.files[0];
            if (!file) {
                showToast('Please upload an image first.', 'danger');
                return;
            }

            const formData = new FormData(uploadForm);
            
            // Show loading overlay
            loadingOverlay.classList.remove('hidden');
            loadingStep.innerText = "Uploading image and sending to OpenAI Vision API...";
            
            try {
                // Simulate step text changes
                const stepTimer = setTimeout(() => {
                    loadingStep.innerText = "Analyzing image and generating caption...";
                }, 3000);
                
                const stepTimer2 = setTimeout(() => {
                    loadingStep.innerText = "Generating voiceover with OpenAI TTS...";
                }, 7000);

                const response = await fetch('/generate', {
                    method: 'POST',
                    body: formData
                });
                
                clearTimeout(stepTimer);
                clearTimeout(stepTimer2);
                
                const data = await response.json();
                
                if (!response.ok) {
                    throw new Error(data.error || 'Failed to process request');
                }
                
                // Display results
                resultImage.src = `/static/uploads/images/${data.image_filename}`;
                resultCaption.innerText = data.caption;
                resultAudio.src = `/static/uploads/audio/${data.audio_filename}`;
                resultAudio.load();
                
                downloadAudioBtn.href = `/static/uploads/audio/${data.audio_filename}`;
                
                resultCard.classList.remove('hidden');
                resultCard.scrollIntoView({ behavior: 'smooth' });
                
                showToast('Caption and voiceover generated successfully!', 'success');
                
                // Add to history
                addHistoryItemToDOM(data);
                
            } catch (error) {
                console.error(error);
                showToast(error.message, 'danger');
            } finally {
                loadingOverlay.classList.add('hidden');
            }
        });
    }

    // Copy to clipboard function
    if (copyBtn) {
        copyBtn.addEventListener('click', () => {
            const caption = resultCaption.innerText;
            navigator.clipboard.writeText(caption).then(() => {
                const originalText = copyBtn.innerHTML;
                copyBtn.innerHTML = '<i class="fa-solid fa-check"></i> Copied!';
                showToast('Copied caption text to clipboard.', 'success');
                setTimeout(() => {
                    copyBtn.innerHTML = originalText;
                }, 2000);
            }).catch(err => {
                console.error('Could not copy text: ', err);
            });
        });
    }

    // Add generated item dynamically to history DOM
    function addHistoryItemToDOM(item) {
        if (noHistoryMsg) {
            noHistoryMsg.remove();
        }
        
        const historyItem = document.createElement('div');
        historyItem.className = 'history-item glass-card-nested';
        historyItem.id = `history-item-${item.id}`;
        
        // Format timestamp
        const now = new Date();
        const formattedDate = now.toISOString().slice(0, 10) + ' ' + now.toTimeString().slice(0, 5);
        
        historyItem.innerHTML = `
            <div class="history-image">
                <img src="/static/uploads/images/${item.image_filename}" alt="History Image">
            </div>
            <div class="history-details">
                <p class="history-caption">${item.caption}</p>
                <div class="history-meta">
                    <span class="voice-badge"><i class="fa-solid fa-comment-dots"></i> Voice: ${item.voice}</span>
                    <span class="date-badge"><i class="fa-solid fa-calendar-day"></i> ${formattedDate}</span>
                </div>
                <div class="history-audio">
                    <audio src="/static/uploads/audio/${item.audio_filename}" controls class="history-audio-player"></audio>
                </div>
                <div class="history-actions">
                    <button class="delete-btn" onclick="deleteHistoryItem(${item.id})">
                        <i class="fa-solid fa-trash-can"></i> Delete
                    </button>
                </div>
            </div>
        `;
        
        // Insert at the beginning of history list
        if (historyGrid.firstChild) {
            historyGrid.insertBefore(historyItem, historyGrid.firstChild);
        } else {
            historyGrid.appendChild(historyItem);
        }
    }
});

// Delete history helper (exposed globally for the inline onclick)
async function deleteHistoryItem(id) {
    if (!confirm('Are you sure you want to delete this caption record?')) {
        return;
    }
    
    try {
        const response = await fetch(`/history/delete/${id}`, {
            method: 'POST'
        });
        
        const data = await response.json();
        if (response.ok) {
            const element = document.getElementById(`history-item-${id}`);
            if (element) {
                element.style.opacity = '0';
                element.style.transform = 'scale(0.9)';
                setTimeout(() => {
                    element.remove();
                    
                    // Show custom success toast
                    const container = document.getElementById('global-alert-container');
                    if (container) {
                        const toast = document.createElement('div');
                        toast.className = 'glass-alert alert-success';
                        toast.innerHTML = `
                            <i class="fa-solid fa-circle-check alert-icon"></i>
                            <span class="alert-text">Record deleted successfully.</span>
                            <button class="alert-close-btn" onclick="this.parentElement.remove();">&times;</button>
                        `;
                        container.appendChild(toast);
                        // Auto dismiss after 4.5 seconds
                        setTimeout(() => {
                            toast.classList.add('fade-out');
                            setTimeout(() => toast.remove(), 350);
                        }, 4500);
                    }

                    // If no items left, show placeholder
                    const historyGrid = document.getElementById('history-grid');
                    if (historyGrid && historyGrid.children.length === 0) {
                        historyGrid.innerHTML = `
                            <div class="no-history" id="no-history-msg">
                                <i class="fa-regular fa-image no-history-icon"></i>
                                <p>No caption history yet. Upload an image above to get started!</p>
                            </div>
                        `;
                    }
                }, 300);
            }
        } else {
            alert(`Error deleting record: ${data.error}`);
        }
    } catch (error) {
        console.error(error);
        alert('An error occurred while deleting.');
    }
}
