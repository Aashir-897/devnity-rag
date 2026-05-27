/* ============================================
   Devnity AI - Main JavaScript
   ============================================ */

// Mobile sidebar toggle
const mobileMenuBtn = document.getElementById('mobileMenuBtn');
const sidebar = document.getElementById('sidebar');
const mobileOverlay = document.getElementById('mobileOverlay');

if (mobileMenuBtn && sidebar && mobileOverlay) {
    mobileMenuBtn.addEventListener('click', () => {
        sidebar.classList.add('open');
        mobileOverlay.classList.add('show');
    });

    mobileOverlay.addEventListener('click', () => {
        sidebar.classList.remove('open');
        mobileOverlay.classList.remove('show');
    });
}

// Auto-dismiss flash messages
const flashMessages = document.querySelectorAll('.flash-message');
flashMessages.forEach(msg => {
    setTimeout(() => {
        msg.style.opacity = '0';
        msg.style.transform = 'translateX(100%)';
        setTimeout(() => msg.remove(), 300);
    }, 5000);
});

/* ============================================
   Upload Functionality
   ============================================ */

const uploadZone = document.getElementById('uploadZone');
const fileInput = document.getElementById('fileInput');
const browseBtn = document.getElementById('browseBtn');
const processingOverlay = document.getElementById('processingOverlay');

if (uploadZone && fileInput) {
    // Click to browse
    uploadZone.addEventListener('click', (e) => {
        if (e.target !== browseBtn && !browseBtn.contains(e.target)) {
            fileInput.click();
        }
    });

    if (browseBtn) {
        browseBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            fileInput.click();
        });
    }

    // Drag and drop
    uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadZone.classList.add('dragover');
    });

    uploadZone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
    });

    uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadZone.classList.remove('dragover');

        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFileUpload(files[0]);
        }
    });

    // File input change
    fileInput.addEventListener('change', (e) => {
        const files = e.target.files;
        if (files.length > 0) {
            handleFileUpload(files[0]);
        }
    });
}

// Handle file upload
async function handleFileUpload(file) {
    if (file.type !== 'application/pdf') {
        if (typeof showToast === 'function') showToast('Please upload a PDF file', 'error');
        else alert('Please upload a PDF file');
        return;
    }

    if (file.size > 30 * 1024 * 1024) {
        if (typeof showToast === 'function') showToast('File size must be less than 30MB', 'error');
        else alert('File size must be less than 30MB');
        return;
    }

    // Show processing overlay
    const processingFilename = document.getElementById('processingFilename');
    const processingProgressFill = document.getElementById('processingProgressFill');
    const processingPercentage = document.getElementById('processingPercentage');
    const processingSteps = document.getElementById('processingSteps');
    const processingMessage = document.getElementById('processingMessage');
    const processingError = document.getElementById('processingError');
    const processingErrorText = document.getElementById('processingErrorText');
    const processingClose = document.getElementById('processingClose');
    const processingDismiss = document.getElementById('processingDismiss');

    processingFilename.textContent = file.name;
    processingOverlay.style.display = 'flex';
    processingError.style.display = 'none';

    const steps = ['Extracting', 'OCR', 'Images', 'Embeddings', 'Summary'];
    let currentStep = 0;

    // Update step display
    function updateStepDisplay(step, progress, message) {
        processingSteps.innerHTML = steps.map((s, i) => {
            let status = 'pending';
            if (s === step) status = 'active';
            else if (steps.indexOf(step) > i) status = 'done';

            return `
                <div class="processing-step ${status}">
                    <span class="processing-step-dot"></span>
                    <span class="processing-step-text">${s}</span>
                </div>
            `;
        }).join('');

        processingProgressFill.style.width = progress + '%';
        processingPercentage.textContent = progress + '%';
        processingMessage.textContent = message;
    }

    // Create form data
    const formData = new FormData();
    formData.append('pdf', file);

    try {
        // Upload with progress
        updateStepDisplay('Extracting', 10, 'Starting upload...');

        // Use XMLHttpRequest for progress tracking
        const xhr = new XMLHttpRequest();

        const uploadPromise = new Promise((resolve, reject) => {
            xhr.upload.addEventListener('progress', (e) => {
                if (e.lengthComputable) {
                    const progress = Math.round((e.loaded / e.total) * 20);
                    updateStepDisplay('Extracting', progress, 'Uploading file...');
                }
            });

            xhr.addEventListener('load', () => {
                if (xhr.status === 200) {
                    resolve(JSON.parse(xhr.responseText));
                } else {
                    reject(new Error('Upload failed'));
                }
            });

            xhr.addEventListener('error', () => reject(new Error('Upload failed')));

            xhr.open('POST', '/upload');
            xhr.send(formData);
        });

        const uploadResult = await uploadPromise;

        // Simulate processing steps (in production, use SSE endpoint)
        const processingStepsData = [
            { step: 'OCR', progress: 30, message: 'Running OCR on images...' },
            { step: 'Images', progress: 50, message: 'Processing images...' },
            { step: 'Embeddings', progress: 75, message: 'Generating embeddings...' },
            { step: 'Summary', progress: 90, message: 'Creating AI summary...' },
        ];

        for (const stepData of processingStepsData) {
            await new Promise(resolve => setTimeout(resolve, 800));
            updateStepDisplay(stepData.step, stepData.progress, stepData.message);
        }

        // Complete
        updateStepDisplay('Summary', 100, 'Processing complete! Redirecting...');

        setTimeout(() => {
            window.location.href = `/study/${uploadResult.pdf_id}`;
        }, 1000);

    } catch (err) {
        console.error('Upload error:', err);
        processingError.style.display = 'block';
        processingErrorText.textContent = 'Failed to process PDF. Please try again.';
    }

    // Close handlers
    if (processingClose) {
        processingClose.onclick = () => {
            processingOverlay.style.display = 'none';
        };
    }

    if (processingDismiss) {
        processingDismiss.onclick = () => {
            processingOverlay.style.display = 'none';
        };
    }
}

/* ============================================
   SSE Progress (for real-time processing)
   ============================================ */

function connectToProgressStream(pdfId) {
    const eventSource = new EventSource(`/progress/${pdfId}`);

    eventSource.addEventListener('message', (e) => {
        const data = JSON.parse(e.data);

        // Update progress UI
        updateStepDisplay(data.step, data.progress, data.message);

        if (data.done) {
            eventSource.close();
            window.location.href = `/study/${pdfId}`;
        }

        if (data.error) {
            eventSource.close();
            const processingError = document.getElementById('processingError');
            const processingErrorText = document.getElementById('processingErrorText');
            processingError.style.display = 'block';
            processingErrorText.textContent = data.message;
        }
    });

    eventSource.addEventListener('error', () => {
        eventSource.close();
    });
}

/* ============================================
   Utility Functions
   ============================================ */

// Format date
function formatDate(dateString) {
    const date = new Date(dateString);
    const options = { month: 'short', day: 'numeric', year: 'numeric' };
    return date.toLocaleDateString('en-US', options);
}

// Format file size
function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

// CSRF token helper
function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
}

// Fetch with CSRF
async function fetchWithCsrf(url, options = {}) {
    const csrfToken = getCsrfToken();
    const headers = {
        ...options.headers,
        'X-CSRFToken': csrfToken,
    };

    return fetch(url, { ...options, headers });
}

/* ============================================
   Keyframe animations (CSS fallback)
   ============================================ */

// Add keyframes for spin animation if not in CSS
const style = document.createElement('style');
style.textContent = `
    @keyframes spin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }
`;
document.head.appendChild(style);
