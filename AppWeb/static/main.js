document.addEventListener('DOMContentLoaded', () => {
    console.log('=== SISTEMA INICIADO ===');
    
    // === CONFIGURACIÓN Y VARIABLES GLOBALES ===
    let isProcessing = false;

    // === ELEMENTOS DEL DOM ===
    const fileInput = document.getElementById('file-input');
    const resultsGrid = document.getElementById('results-grid');
    const welcomeMessage = document.querySelector('.welcome-message');
    const loader = document.getElementById('loader');
    const progressText = document.getElementById('progress-text');
    const timeLabel = document.getElementById('current-time');
    const fileDropZone = document.querySelector('.file-drop-zone');
    
    // Modal elements
    const modal = document.getElementById('details-modal');
    const modalBody = document.getElementById('modal-body');
    const closeModalButton = document.querySelector('.close-button');

    // Elementos de Grad-CAM
    const gradcamModal = document.getElementById('gradcam-modal');
    const gradcamBody = document.getElementById('gradcam-body');
    const closeGradcamModal = document.getElementById('close-gradcam-modal');
    
    // Elementos de estadísticas y funcionalidades extras
    const statsModal = document.getElementById('stats-modal');
    const closeStatsModal = document.getElementById('close-stats-modal');
    const toggleStatsBtn = document.getElementById('toggle-stats');
    const exportBtn = document.getElementById('export-btn');
    const clearSessionBtn = document.getElementById('clear-session');
    const totalProcessedEl = document.getElementById('total-processed');
    const avgConfidenceEl = document.getElementById('avg-confidence');
    const mostCommonEl = document.getElementById('most-common');
    
    // Elementos de cámara
    const startCameraBtn = document.getElementById('start-camera');
    const stopCameraBtn = document.getElementById('stop-camera');
    const capturePhotoBtn = document.getElementById('capture-photo');
    const switchCameraBtn = document.getElementById('switch-camera');
    const cameraVideo = document.getElementById('camera-video');
    const cameraCanvas = document.getElementById('camera-canvas');
    const cameraArea = document.getElementById('camera-area');
    const cameraStatus = document.getElementById('camera-status');
    const livePrediction = document.getElementById('live-prediction');

    // === VARIABLES DE CÁMARA ===
    let currentStream = null;
    let detectionInterval = null;
    let availableCameras = [];
    let currentCameraIndex = 0;
    let isDetecting = false;

    // === VARIABLES DE ESTADÍSTICAS ===
    let sessionStats = {
        totalProcessed: 0,
        confidenceSum: 0,
        classCount: {},
        confidenceLevels: []
    };
    
    // Emojis de clase para el modal
    const CLASS_EMOJIS = {
        'hormigon': '🏗️', 'ceramico': '🧱', 'piedra': '🏛️', 'yeso': '🎨', 'asfaltico': '🛣️', 'basura_general': '🗑️' 
    };

    const classDisplayNames = {
        hormigon: "Hormigón",
        ceramico: "Cerámico",
        piedra: "Piedra",
        yeso: "Yeso",
        asfaltico: "Asfáltico",
        basura_general: "Basura General"
    };
    
    // === FUNCIONES DE UTILIDAD ===
    function showNotification(message, type = 'success') {
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: ${type === 'success' ? '#27ae60' : type === 'error' ? '#e74c3c' : '#3498db'};
            color: white;
            padding: 1rem;
            border-radius: 5px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            z-index: 10000;
            font-weight: bold;
            max-width: 300px;
        `;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.style.opacity = '0';
            notification.style.transform = 'translateX(100%)';
            notification.style.transition = 'all 0.3s ease';
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }

    // === EVENT LISTENERS BÁSICOS ===
    // Manejar click en la zona de drop
    fileDropZone.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        console.log('Click en zona de drop, isProcessing:', isProcessing);
        if (!isProcessing) {
            fileInput.click();
        }
    });

    // Manejar drag and drop
    fileDropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        e.stopPropagation();
        fileDropZone.style.borderColor = '#2c3e50';
        fileDropZone.style.backgroundColor = '#e9ecef';
    });

    fileDropZone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        e.stopPropagation();
        fileDropZone.style.borderColor = '#3498db';
        fileDropZone.style.backgroundColor = '#f8f9fa';
    });

    fileDropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        e.stopPropagation();
        fileDropZone.style.borderColor = '#3498db';
        fileDropZone.style.backgroundColor = '#f8f9fa';
        
        const files = e.dataTransfer.files;
        console.log('Drop detectado, archivos:', files.length, 'isProcessing:', isProcessing);
        if (files.length > 0 && !isProcessing) {
            processFiles(files);
        }
    });

    // Manejar selección de archivos - ANÁLISIS AUTOMÁTICO
    fileInput.addEventListener('change', (e) => {
        const files = e.target.files;
        console.log('Cambio en input detectado, archivos:', files.length, 'isProcessing:', isProcessing);
        
        // Usar setTimeout para evitar conflictos de eventos
        setTimeout(() => {
            if (files.length > 0 && !isProcessing) {
                processFiles(files);
            }
            // Limpiar el input después del procesamiento
            e.target.value = '';
        }, 100);
    });

    // Función para procesar archivos automáticamente
    async function processFiles(files) {
        console.log('=== INICIANDO processFiles ===');
        console.log('Archivos recibidos:', files.length);
        console.log('isProcessing al inicio:', isProcessing);
        
        if (files.length === 0) {
            console.log('No hay archivos para procesar');
            return;
        }
        
        if (isProcessing) {
            console.log('Ya se está procesando, cancelando');
            return;
        }

        isProcessing = true;
        console.log('isProcessing establecido a true');

        try {
            // Validar archivos antes de procesarlos
            const validFiles = [];
            
            for (const file of files) {
                console.log('Validando archivo:', file.name, 'Tipo:', file.type);
                if (!file.type.startsWith('image/')) {
                    alert(i18next.t('file_not_image', { filename: file.name }));
                    //alert(`El archivo "${file.name}" no es una imagen válida.`);
                    continue;
                }
                
                validFiles.push(file);
            }

            console.log('Archivos válidos:', validFiles.length);

            if (validFiles.length === 0) {
                console.log('No hay archivos válidos');
                isProcessing = false;
                return;
            }

            // Mostrar estado de carga
            console.log('Mostrando estado de carga');
            if (welcomeMessage) {
                welcomeMessage.style.display = 'none';
                console.log('Welcome message ocultado');
            }
            resultsGrid.innerHTML = '';
            loader.style.display = 'block';
            // progressText.textContent = `Analizando ${validFiles.length} imagen(es) automáticamente...`;
            progressText.textContent = i18next.t('processing_images_automatically', { count: validFiles.length });
            const formData = new FormData();
            for (const file of validFiles) {
                formData.append('files', file);
            }

            console.log(`Enviando ${validFiles.length} archivos al servidor...`);

            const response = await fetch('/classify', {
                method: 'POST',
                body: formData,
                timeout: 120000 // 2 minutos timeout
            });

            console.log('Respuesta del servidor recibida, status:', response.status);

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || `Error del servidor: ${response.status} ${response.statusText}`);
            }

            const data = await response.json();
            console.log('Datos del servidor:', data);
            
            if (data.results && data.results.length > 0) {
                console.log('Mostrando resultados:', data.results.length);
                displayResults(data.results);
                
                // Actualizar estadísticas con los nuevos resultados
                updateLocalStats(data.results);
                
                //progressText.textContent = `Análisis completado: ${data.results.length} imagen(es) procesadas.`;
                progressText.textContent = i18next.t('analysis_completed', { count: data.results.length });
                //showNotification(`✅ ${data.results.length} imagen(es) procesadas exitosamente`, 'success');
                showNotification(i18next.t('images_processed_success', { count: data.results.length }), 'success');
            } else {
                throw new Error('No se obtuvieron resultados válidos del servidor.');
            }

        } catch (error) {
            console.error('Error:', error);
            
            // Mejorar el manejo de errores específicos
            //let errorMessage = 'Ocurrió un error durante el análisis.';
            let errorMessage = i18next.t('error_generic');

            if (error.message.includes('413') || error.message.includes('Entity Too Large')) {
                //errorMessage = 'Las imágenes son demasiado grandes. Intenta con imágenes más pequeñas.';
                errorMessage = i18next.t('error_too_large');
            } else if (error.message.includes('Failed to fetch')) {
                //errorMessage = 'Error de conexión. Verifica tu conexión a internet e inténtalo de nuevo.';
                errorMessage = i18next.t('error_connection');
            } else if (error.message.includes('timeout')) {
                //errorMessage = 'El procesamiento está tomando demasiado tiempo. Intenta con menos imágenes.';
                errorMessage = i18next.t('error_timeout');
            }
            
            progressText.textContent = errorMessage;
            /*resultsGrid.innerHTML = `
                <div style="text-align: center; color: red; padding: 20px;">
                    <h3>❌ Error en el Análisis</h3>
                    <p>${errorMessage}</p>
                    <p style="font-size: 0.9em; color: #666; margin-top: 10px;">Detalles técnicos: ${error.message}</p>
                    <button onclick="location.reload()" style="margin-top: 15px; padding: 10px 20px; background: #3498db; color: white; border: none; border-radius: 5px; cursor: pointer;">
                        🔄 Reintentar
                    </button>
                </div>
            `;*/
            resultsGrid.innerHTML = `
                <div style="text-align: center; color: red; padding: 20px;">
                    <h3>${i18next.t('error_analysis_title')}</h3>
                    <p>${errorMessage}</p>
                    <p style="font-size: 0.9em; color: #666; margin-top: 10px;">Detalles técnicos: ${error.message}</p>
                    <button onclick="location.reload()" style="margin-top: 15px; padding: 10px 20px; background: #3498db; color: white; border: none; border-radius: 5px; cursor: pointer;">
                        ${i18next.t('retry')}
                    </button>
                </div>
            `;
        } finally {
            console.log('=== FINALIZANDO processFiles ===');
            loader.style.display = 'none';
            isProcessing = false;
            console.log('isProcessing establecido a false');
        }
    }

    // Función para mostrar los resultados en la grilla
    function displayResults(results) {
        resultsGrid.innerHTML = '';
        if (results.length === 0) {
            // resultsGrid.innerHTML = '<p>No se obtuvieron resultados válidos.</p>';
            resultsGrid.innerHTML = i18next.t('no_valid_results');
            return;
        }

        results.forEach(result => {
            const card = createResultCard(result);
            resultsGrid.appendChild(card);
        });
    }

    // Función para crear una tarjeta de resultado
    function createResultCard(result) {
        const card = document.createElement('div');
        card.className = 'result-card';

        const confidenceColor = getConfidenceColor(result.confidence);
        
        // Generar lista de probabilidades > 50%
        const probsHTML = result.probabilities
            .filter(prob => prob.probability > 50)
            .map(prob => {
                const color = getConfidenceColor(prob.probability);
                const emoji = CLASS_EMOJIS[prob.class_name] || '📦';

                /*return `<div style="font-size: 0.8em; color: ${color}; margin-bottom: 2px;">
                            ${emoji} ${classDisplayNames[prob.class_name] || prob.class_name}: ${prob.probability.toFixed(1)}%
                        </div>`;*/
                const materialTranslated = i18next.t(`materials.${prob.class_name}`);
                return `<div style="font-size: 0.8em; color: ${color}; margin-bottom: 2px;">
                            ${emoji} ${materialTranslated}: ${prob.probability.toFixed(1)}%
                        </div>`;
            }).join('');

        /*card.innerHTML = `
            <img src="${result.image_url}" alt="${result.filename}" 
                 onerror="this.onerror=null; this.src='data:image/svg+xml;charset=utf-8,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%22200%22 height=%22150%22 viewBox=%220 0 200 150%22><rect width=%22200%22 height=%22150%22 fill=%22%23f8f9fa%22 stroke=%22%23dee2e6%22/><text x=%2250%25%22 y=%2250%25%22 font-family=%22Arial%22 font-size=%2214%22 fill=%22%23666%22 text-anchor=%22middle%22 dy=%22.3em%22>Error cargando</text></svg>';">
            <div class="info">
                <h4>${result.filename}</h4>
                <div class="prediction" style="background-color: ${result.color}; color: white;">
                    ${result.emoji} ${classDisplayNames[result.predicted_class] || result.predicted_class}
                </div>
                <p class="confidence">
                    Confianza: <span style="color: ${confidenceColor};">${result.confidence.toFixed(1)}%</span>
                </p>
                <div class="probabilities-list">
                    ${probsHTML}
                </div>
                <button class="details-button">📊 Ver Probabilidades</button>
                <button class="gradcam-button">🗺️ Ver mapa de zonas</button>
            </div>
        `;*/
        const predictedTranslated = i18next.t(`materials.${result.predicted_class}`);
        card.innerHTML = `
            <img src="${result.image_url}" alt="${result.filename}" 
                 onerror="this.onerror=null; this.src='data:image/svg+xml;charset=utf-8,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%22200%22 height=%22150%22 viewBox=%220 0 200 150%22><rect width=%22200%22 height=%22150%22 fill=%22%23f8f9fa%22 stroke=%22%23dee2e6%22/><text x=%2250%25%22 y=%2250%25%22 font-family=%22Arial%22 font-size=%2214%22 fill=%22%23666%22 text-anchor=%22middle%22 dy=%22.3em%22>Error cargando</text></svg>';">
            <div class="info">
                <h4>${result.filename}</h4>
                <div class="prediction" style="background-color: ${result.color}; color: white;">
                    ${result.emoji} ${predictedTranslated}
                </div>
                <p class="confidence">
                    ${i18next.t('confidence_label')} <span style="color: ${confidenceColor};">${result.confidence.toFixed(1)}%</span>
                </p>
                <div class="probabilities-list">
                    ${probsHTML}
                </div>
                <button class="details-button">${i18next.t('view_probabilities')}</button>
                <button class="gradcam-button">${i18next.t('view_heatmap')}</button>
            </div>
        `;

        // Abrir imagen en nueva pestaña al hacer clic en la imagen
        const imgElement = card.querySelector('img');
        imgElement.style.cursor = 'pointer'; // para que el usuario vea que se puede clicar
        //imgElement.title = 'Ver imagen';     // mensaje al pasar el ratón
        imgElement.title = i18next.t('view_image');
        imgElement.addEventListener('click', () => {
            window.open(result.image_url, '_blank'); // abre la imagen en otra pestaña
        });

        // Event listener para el botón de detalles
        card.querySelector('.details-button').addEventListener('click', () => {
            showDetailsModal(result);
        });

        // Event listener para el botón de Grad-CAM
        card.querySelector('.gradcam-button').addEventListener('click', () => {
            showGradcamModal(result);
        });

        return card;
    }

    // Función para obtener color según confianza
    function getConfidenceColor(confidence) {
        if (confidence >= 80) return '#27ae60';
        if (confidence >= 50) return '#f39c12';
        return '#e74c3c';
    }

    // Función para mostrar el modal con detalles
    function showDetailsModal(result) {
        // let probabilitiesHTML = '<div id="modal-probs"><h3>📊 Probabilidades por Clase</h3>';
        let probabilitiesHTML = i18next.t('probabilities_HTML');
        
        result.probabilities.forEach((prob, index) => {
            const color = getConfidenceColor(prob.probability);
            const emoji = CLASS_EMOJIS[prob.class_name] || '📦';
            const percentage = prob.probability.toFixed(1);
            const widthPercentage = Math.max(prob.probability, 1); // Mínimo 1% para visibilidad
            const materialTranslated = i18next.t(`materials.${prob.class_name}`);
            
            // Debug: Log para verificar los valores
            if (index < 3) { // Solo los primeros 3 para no llenar la consola
                console.log(`${prob.class_name}: ${percentage}% -> width: ${widthPercentage}%`);
            }
            /*
            probabilitiesHTML += `
                <div class="prob-bar-container">
                    <div class="prob-bar-label">
                        <span>${emoji} ${classDisplayNames[prob.class_name] || prob.class_name}</span>
                        <span style="color: ${color}; font-weight: bold;">${percentage}%</span>
                    </div>
                    <div class="prob-bar" style="background-color: #e9ecef; border-radius: 5px; height: 20px; position: relative; overflow: hidden;">
                        <div style="width: ${widthPercentage}%; background-color: ${color}; height: 100%; border-radius: 5px; position: relative; transition: width 0.3s ease;">
                            <span class="prob-bar-text" style="position: absolute; right: 5px; top: 50%; transform: translateY(-50%); color: white; font-size: 0.75rem; font-weight: bold;">${percentage}%</span>
                        </div>
                    </div>
                </div>
            `;*/

            
            probabilitiesHTML += `
                <div class="prob-bar-container">
                    <div class="prob-bar-label">
                        <span>${emoji} ${materialTranslated}</span>
                        <span style="color: ${color}; font-weight: bold;">${percentage}%</span>
                    </div>
                    <div class="prob-bar" style="background-color: #e9ecef; border-radius: 5px; height: 20px; position: relative; overflow: hidden;">
                        <div style="width: ${widthPercentage}%; background-color: ${color}; height: 100%; border-radius: 5px; position: relative; transition: width 0.3s ease;">
                            <span class="prob-bar-text" style="position: absolute; right: 5px; top: 50%; transform: translateY(-50%); color: white; font-size: 0.75rem; font-weight: bold;">${percentage}%</span>
                        </div>
                    </div>
                </div>
            `;
        });
        probabilitiesHTML += '</div>';

        /*
        modalBody.innerHTML = `
            <div style="display: flex; gap: 20px; align-items: flex-start;">
            <img src="${result.image_url}" alt="${result.filename}" 
                style="max-width: 250px; max-height: 200px; object-fit: contain; border-radius: 8px; background-color: #f8f9fa; cursor: pointer;"
                title="Ver imagen"
                onclick="window.open('${result.image_url}', '_blank');"
                onerror="this.style.display='none';">
                <div style="flex: 1;">
                    <h2>${result.filename}</h2>
                    <div style="margin: 15px 0; padding: 10px; background: ${result.color}; color: white; border-radius: 8px; text-align: center;">
                        <strong>${result.emoji} ${classDisplayNames[result.predicted_class] || result.predicted_class}</strong><br>
                        <span>Confianza: ${result.confidence.toFixed(1)}%</span>
                    </div>
                    ${probabilitiesHTML}
                </div>
            </div>
        `;*/
        
        const predictedTranslated = i18next.t(`materials.${result.predicted_class}`);
        modalBody.innerHTML = `
            <div style="display: flex; gap: 20px; align-items: flex-start;">
            <img src="${result.image_url}" alt="${result.filename}" 
                style="max-width: 250px; max-height: 200px; object-fit: contain; border-radius: 8px; background-color: #f8f9fa; cursor: pointer;"
                title="Ver imagen"
                onclick="window.open('${result.image_url}', '_blank');"
                onerror="this.style.display='none';">
                <div style="flex: 1;">
                    <h2>${result.filename}</h2>
                    <div style="margin: 15px 0; padding: 10px; background: ${result.color}; color: white; border-radius: 8px; text-align: center;">
                        <strong>${result.emoji} ${predictedTranslated}</strong><br>
                        <span>${i18next.t('confidence_label')} ${result.confidence.toFixed(1)}%</span>
                    </div>
                    ${probabilitiesHTML}
                </div>
            </div>
        `;
        modal.style.display = 'block';
    }

    // Cerrar el modal
    closeModalButton.onclick = () => {
        modal.style.display = 'none';
    };
    
    window.onclick = (event) => {
        if (event.target == modal) {
            modal.style.display = 'none';
        }
    };

    // Función para mostrar el modal de Grad-CAM
    function showGradcamModal(result) {
        //gradcamBody.innerHTML = '<p>🔄 Generando mapas Grad-CAM...</p>';
        gradcamBody.innerHTML = `<p>🔄 ${i18next.t('generating_gradcam')}...</p>`;
        gradcamModal.style.display = 'block';

        fetch('/api/gradcam', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename: result.filename })
        })
        .then(response => response.json())
        .then(data => {
            gradcamBody.innerHTML = ''; // Limpiar loader

            if (data.heatmap_urls && data.heatmap_urls.length > 0) {
                data.heatmap_urls.forEach(url => {
                    const wrapper = document.createElement('div');
                    wrapper.style = 'text-align: center; margin-bottom: 15px;';

                    const urlFilename = url.split('/').pop(); // gradcam_120755_basura_general.jpg
                    const match = urlFilename.match(/gradcam_.+?_([a-z_]+)\.jpg$/);
                    const className = match ? match[1] : 'desconocido';

                    const emoji = CLASS_EMOJIS[className] || '📦';
                    //const readableName = classDisplayNames[className] || className;
                    const readableName = i18next.t(`materials.${className}`) || className;

                    const title = document.createElement('div');
                    title.innerHTML = `${emoji} ${readableName}`;
                    title.style = 'margin-bottom: 5px; font-weight: bold;';

                    const img = document.createElement('img');
                    img.src = url;
                    img.alt = 'Grad-CAM ' + className;
                    img.style = 'max-width: 100%; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.2);';

                    wrapper.appendChild(title);
                    wrapper.appendChild(img);
                    gradcamBody.appendChild(wrapper);
                });
            } else {
                //gradcamBody.innerHTML = '<p>⚠️ No se generaron mapas Grad-CAM para esta imagen.</p>';
                gradcamBody.innerHTML = `<p>⚠️ ${i18next.t('no_gradcam_generated')}</p>`;
            }
        })
        .catch(error => {
            console.error('Error obteniendo Grad-CAM:', error);
            //gradcamBody.innerHTML = '<p>❌ Error generando mapas Grad-CAM.</p>';
            gradcamBody.innerHTML = `<p>❌ ${i18next.t('error_generating_gradcam')}</p>`;
        });
    }
    // Cerrar el modal de Grad-CAM
    closeGradcamModal.onclick = () => {
        gradcamModal.style.display = 'none';
        gradcamBody.innerHTML = '';
    };

    window.onclick = (event) => {
        if (event.target == gradcamModal) {
            gradcamModal.style.display = 'none';
            gradcamBody.innerHTML = '';
        }
    };
    
    // Actualizar la hora en el footer
    function updateTime() {
        if (timeLabel) {
            const now = new Date();
            timeLabel.textContent = now.toLocaleString('es-ES');
        }
    }
    
    setInterval(updateTime, 1000);
    updateTime();

    // === FUNCIONES DE CÁMARA ===
    async function initCamera() {
        try {
            // Enumerar cámaras disponibles
            const devices = await navigator.mediaDevices.enumerateDevices();
            availableCameras = devices.filter(device => device.kind === 'videoinput');
            
            if (availableCameras.length === 0) {
                throw new Error(i18next.t('no_camera_found'));
            }
            
            // Configurar botones según las cámaras disponibles
            if (availableCameras.length > 1) {
                switchCameraBtn.style.display = 'inline-block';
            }
            
            await startCamera();
            
        } catch (error) {
            console.error('Error inicializando cámara:', error);
            updateCameraStatus('Error: ' + error.message, 'error');
        }
    }
    
    async function startCamera() {
        try {
            // Detener stream actual si existe
            if (currentStream) {
                stopCamera();
            }
            
            const constraints = {
                video: {
                    deviceId: availableCameras[currentCameraIndex]?.deviceId,
                    width: { ideal: 640 },
                    height: { ideal: 480 },
                    facingMode: availableCameras.length > 1 ? 'environment' : 'user'
                }
            };
            
            currentStream = await navigator.mediaDevices.getUserMedia(constraints);
            cameraVideo.srcObject = currentStream;
            
            // Esperar a que el video esté listo
            await new Promise(resolve => {
                cameraVideo.onloadedmetadata = resolve;
            });
            
            // Configurar canvas con las dimensiones del video
            cameraCanvas.width = cameraVideo.videoWidth;
            cameraCanvas.height = cameraVideo.videoHeight;
            
            // Mostrar área de cámara
            cameraArea.style.display = 'block';
            resultsGrid.style.display = 'none';

            // Ocultar status-area al iniciar la cámara
            const statusArea = document.getElementById('status-area');
            if (statusArea) {
                statusArea.style.display = 'none';
            }
            
            // Actualizar controles
            startCameraBtn.style.display = 'none';
            stopCameraBtn.style.display = 'inline-block';
            capturePhotoBtn.style.display = 'inline-block';
            
            updateCameraStatus(i18next.t('camera_connected'), 'connected');
            
            // Iniciar detección automática
            startDetection();
            
        } catch (error) {
            console.error('Error iniciando cámara:', error);
            // Si se quiere mantener el mensaje original de error en inglés
            updateCameraStatus(i18next.t('camera_error') + ': ' + error.message, 'error');

            // O si se prefiere solo el texto traducido
            //updateCameraStatus(i18next.t('camera_error'), 'error');
        }
    }
    
    function stopCamera() {
        if (currentStream) {
            currentStream.getTracks().forEach(track => track.stop());
            currentStream = null;
        }
        
        if (detectionInterval) {
            clearInterval(detectionInterval);
            detectionInterval = null;
        }
        
        isDetecting = false;
        
        // Ocultar área de cámara
        cameraArea.style.display = 'none';
        resultsGrid.style.display = 'block';

        // Mostrar de nuevo status-area al detener la cámara
        const statusArea = document.getElementById('status-area');
        if (statusArea) {
            statusArea.style.display = 'block';
        }
        
        // Actualizar controles
        startCameraBtn.style.display = 'inline-block';
        stopCameraBtn.style.display = 'none';
        capturePhotoBtn.style.display = 'none';
        
        updateCameraStatus(i18next.t('camera_disconnected'), '');
        
        // Limpiar predicción en vivo
        updateLivePrediction(i18next.t('prediction_class_no_data'), '', '');
    }
    
    async function switchCamera() {
        if (availableCameras.length <= 1) return;
        
        currentCameraIndex = (currentCameraIndex + 1) % availableCameras.length;
        await startCamera();
    }
    
    function startDetection() {
        if (isDetecting) return;
        
        isDetecting = true;
        detectionInterval = setInterval(async () => {
            if (!currentStream || !cameraVideo.videoWidth) return;
            
            try {
                await detectFromVideo();
            } catch (error) {
                console.error('Error en detección:', error);
            }
        }, 1000); // Detectar cada segundo
    }
    
    async function detectFromVideo() {
        if (!cameraVideo.videoWidth || !cameraVideo.videoHeight) return;
        
        const canvas = cameraCanvas;
        const ctx = canvas.getContext('2d');
        
        // Capturar frame del video
        canvas.width = cameraVideo.videoWidth;
        canvas.height = cameraVideo.videoHeight;
        ctx.drawImage(cameraVideo, 0, 0);
        
        // Convertir a blob
        canvas.toBlob(async (blob) => {
            try {
                const formData = new FormData();
                formData.append('files', blob, 'camera_frame.jpg');
                
                const response = await fetch('/classify/camera', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                
                if (data.result) {
                    const result = data.result;
                    const materialTranslated = i18next.t(`materials.${result.predicted_class}`);
                    updateLivePrediction(
                        //`${result.emoji} ${result.display_name}`,
                        `${result.emoji} ${materialTranslated}`,
                        `${result.confidence.toFixed(1)}%`,
                        result.timestamp
                    );
                    
                    // Actualizar estadísticas (sin el updateLocalStats ya que es solo para detección)
                    // updateLocalStats(result);
                }
                
            } catch (error) {
                console.error('Error en detección en tiempo real:', error);
            }
        }, 'image/jpeg', 0.7); // Menor calidad para mayor velocidad
    }
    
    function capturePhoto() {
        if (!cameraVideo.videoWidth || !cameraVideo.videoHeight) return;
        
        const canvas = cameraCanvas;
        const ctx = canvas.getContext('2d');
        
        canvas.width = cameraVideo.videoWidth;
        canvas.height = cameraVideo.videoHeight;
        ctx.drawImage(cameraVideo, 0, 0);
        
        // Convertir a blob y procesar como imagen normal
        canvas.toBlob(async (blob) => {
            try {
                const formData = new FormData();
                formData.append('files', blob, `captura_${Date.now()}.jpg`);

                showNotification(i18next.t('processing_capture'), 'info');
                
                const response = await fetch('/classify', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                
                if (data.results && data.results.length > 0) {
                    // Mostrar resultado en la grilla principal
                    cameraArea.style.display = 'none';
                    resultsGrid.style.display = 'block';

                    // Mostrar de nuevo status-area
                    const statusArea = document.getElementById('status-area');
                    if (statusArea) {
                        statusArea.style.display = 'block';
                    }

                    // Actualizar progress-text para capturas
                    const progressText = document.getElementById('progress-text');
                    if (progressText) {
                        progressText.textContent = i18next.t('analysis_completed_capture');
                    }
                    
                    displayResults(data.results);
                    showNotification(i18next.t('capture_processed_success'), 'success');

                    // Actualizar estadísticas con la captura
                    updateLocalStats(data.results);
                    
                    // Volver al modo cámara después de 3 segundos
                    setTimeout(() => {
                        if (currentStream) {
                            cameraArea.style.display = 'block';
                            resultsGrid.style.display = 'none';
                        }

                        // Ocultar status-area otra vez cuando vuelva la cámara
                        const statusArea = document.getElementById('status-area');
                        const progressText = document.getElementById('progress-text');
                        if (statusArea) {
                            statusArea.style.display = 'none';
                        }
                    }, 3000);
                }
                
            } catch (error) {
                console.error('Error capturando foto:', error);
                showNotification(i18next.t('error_capture'), 'error');
            }
        }, 'image/jpeg', 0.9);
    }
    
    function updateCameraStatus(message, statusClass) { 
        if (cameraStatus) { 
            cameraStatus.textContent = message; 
            cameraStatus.className = 'camera-status ' + statusClass; 
        } 
    }
    
    function updateLivePrediction(classText, confidence, time) {
        if (livePrediction) {
            const classEl = livePrediction.querySelector('.prediction-class');
            const confidenceEl = livePrediction.querySelector('.prediction-confidence');
            const timeEl = livePrediction.querySelector('.prediction-time');
            
            if (classEl) classEl.textContent = classText;
            //if (confidenceEl) confidenceEl.textContent = confidence ? `Confianza: ${confidence}` : 'Confianza: --';
            //if (timeEl) timeEl.textContent = time ? `Última detección: ${time}` : 'Última detección: --';
            if (confidenceEl) confidenceEl.textContent = confidence ? `${i18next.t('prediction_confidence')} ${confidence}` : `${i18next.t('prediction_confidence_no_data')}`;
            if (timeEl) timeEl.textContent = time ? `${i18next.t('last_detection')} ${time}` : `${i18next.t('last_detection_no_data')}`;
        }
    }

    // === FUNCIONES DE ESTADÍSTICAS ===
    // === ESTADÍSTICAS DE SESIÓN ===
    function updateLocalStats(results) {
        // Acepta un único resultado o un array de resultados
        if (!Array.isArray(results)) results = [results];

        results.forEach(result => {
            sessionStats.totalProcessed++;
            sessionStats.confidenceSum += result.confidence;
            sessionStats.classCount[result.predicted_class] = 
                (sessionStats.classCount[result.predicted_class] || 0) + 1;
            sessionStats.confidenceLevels.push(result.confidence / 100); // normalizado 0-1
        });

        localStorage.setItem('sessionStats', JSON.stringify(sessionStats));

        updateStatsDisplay();

        // Habilitar export si hay resultados
        if (exportBtn && sessionStats.totalProcessed > 0) exportBtn.disabled = false;
    }

    function updateStatsDisplay() {
        if (totalProcessedEl) totalProcessedEl.textContent = sessionStats.totalProcessed;

        if (avgConfidenceEl) {
            const avgConf = sessionStats.totalProcessed > 0
                ? (sessionStats.confidenceSum / sessionStats.totalProcessed).toFixed(1)
                : 0;
            avgConfidenceEl.textContent = `${avgConf}%`;
        }

        if (mostCommonEl) {
            const mostCommon = Object.keys(sessionStats.classCount).reduce((a, b) =>
                sessionStats.classCount[a] > sessionStats.classCount[b] ? a : b, null
            );
            if (mostCommon) {
                const emoji = CLASS_EMOJIS[mostCommon] || '';
                //const displayName = classDisplayNames[mostCommon] || mostCommon;
                const displayName = i18next.t(`materials.${mostCommon}`);
                mostCommonEl.textContent = `${emoji} ${displayName} (${sessionStats.classCount[mostCommon]})`;
            } else {
                mostCommonEl.textContent = 'N/A';
            }
        }
    }

    /*
    // Escuchar cuando i18next ya está listo
    document.addEventListener('i18nInitialized', () => {
        // Restaurar sessionStats de localStorage solo cuando i18next ya está listo
        const savedStats = localStorage.getItem('sessionStats');
        if (savedStats) {
            sessionStats = JSON.parse(savedStats);
        }
        // Actualizar estadísticas
        updateStatsDisplay();
    });
    */

    // Restaurar sessionStats y actualizar la UI cuando i18next esté listo y el idioma seleccionado se haya aplicado.
    // Esto evita la situacion donde main.js restaura y pinta antes de que i18next haya cargado las traducciones o antes de que changeLanguage haya terminado.
    function restoreStatsAndUpdate() {
        const savedStats = localStorage.getItem('sessionStats');
        if (savedStats) {
            try {
                sessionStats = JSON.parse(savedStats);
            } catch (e) {
                console.warn('No se pudo parsear sessionStats desde localStorage:', e);
                sessionStats = { totalProcessed: 0, confidenceSum: 0, classCount: {}, confidenceLevels: [] };
            }
        }
        // Actualizar estadísticas (usa i18next.t internamente cuando corresponda)
        updateStatsDisplay();

        // Habilitar export si hay resultados
        if (exportBtn && sessionStats.totalProcessed > 0) exportBtn.disabled = false;
    }

    // Comprueba si hay un idioma guardado por el usuario
    const savedLang = localStorage.getItem('selectedLang');

    if (window.i18next && window.i18next.isInitialized) {
        // i18next ya está inicializado. Si el idioma actual coincide con el guardado (o no hay guardado), restaura ahora.
        if (!savedLang || i18next.language === savedLang) {
            restoreStatsAndUpdate();
        } else {
            // Esperar al cambio de idioma si aún no se ha aplicado
            if (i18next.on) {
                i18next.on('languageChanged', function handler() {
                    restoreStatsAndUpdate();
                    // limpiar handler para evitar ejecuciones futuras innecesarias
                    if (i18next.off) i18next.off('languageChanged', handler);
                });
            } else {
                // Fallback: escucha el evento personalizado
                document.addEventListener('i18nInitialized', restoreStatsAndUpdate, { once: true });
            }
        }
    } else {
        // i18next no está listo aún; esperar al evento de inicialización y luego aplicar la misma lógica
        document.addEventListener('i18nInitialized', () => {
            if (!savedLang || i18next.language === savedLang) {
                restoreStatsAndUpdate();
            } else {
                if (i18next.on) {
                    i18next.on('languageChanged', function handler() {
                        restoreStatsAndUpdate();
                        if (i18next.off) i18next.off('languageChanged', handler);
                    });
                } else {
                    // último recurso: restaurar de todas formas
                    restoreStatsAndUpdate();
                }
            }
        }, { once: true });
    }

    // === MODAL DE ESTADÍSTICAS ===
    let classChartInstance = null;
    let confidenceChartInstance = null;

    function showStatsModal() {
        if (sessionStats.totalProcessed === 0) {
            alert(i18next.t('no_data_stats'));
            return;
        }

        if (statsModal) {
            statsModal.style.display = 'block';
            setTimeout(() => createCharts(), 100); // permitir render del modal
        }
    }

    function createCharts() {
        if (classChartInstance) { classChartInstance.destroy(); classChartInstance = null; }
        if (confidenceChartInstance) { confidenceChartInstance.destroy(); confidenceChartInstance = null; }

        createClassDistributionChart();
        createConfidenceChart();
    }

    function createClassDistributionChart() {
        const ctx = document.getElementById('class-distribution-chart').getContext('2d');
        const classes = Object.keys(classDisplayNames);
        const colors = [
            '#7f8c8d','#d35400','#8e44ad','#f39c12','#34495e','#e74c3c'
        ];
        const values = classes.map(clase => sessionStats.classCount[clase] || 0);

        classChartInstance = new Chart(ctx, {
            type: 'pie',
            data: {
                //labels: classes.map(c => classDisplayNames[c] || c),
                labels: classes.map(c => i18next.t(`materials.${c}`)),
                datasets: [{ data: values, backgroundColor: colors, borderColor: '#fff', borderWidth: 2 }]
            },
            options: {
                responsive: true,
                plugins: {
                    //title: { display: true, text: 'Material con mayor porcentaje por foto' },
                    title: { display: true, text: i18next.t('class_distribution_chart_description') },
                    legend: { position: 'right' }
                }
            }
        });
    }

    function createConfidenceChart() {
        const ctx = document.getElementById('confidence-chart').getContext('2d');
        const ranges = ['0-20%', '21-40%', '41-60%', '61-80%', '81-100%'];
        const counts = [0, 0, 0, 0, 0];

        (sessionStats.confidenceLevels || []).forEach(conf => {
            if (conf <= 0.2) counts[0]++;
            else if (conf <= 0.4) counts[1]++;
            else if (conf <= 0.6) counts[2]++;
            else if (conf <= 0.8) counts[3]++;
            else counts[4]++;
        });

        confidenceChartInstance = new Chart(ctx, {
            type: 'bar',
            //data: { labels: ranges, datasets: [{ label: 'Cantidad', data: counts, backgroundColor: '#3498db', borderColor: '#2980b9', borderWidth: 1 }] },
            data: { labels: ranges, datasets: [{ label: i18next.t('amount'), data: counts, backgroundColor: '#3498db', borderColor: '#2980b9', borderWidth: 1 }] },
            options: {
                responsive: true,
                scales: { y: { beginAtZero: true, precision: 0 } },
                //plugins: { title: { display: true, text: 'Nivel de confianza más alto por foto' }, legend: { display: false } }
                plugins: { title: { display: true, text: i18next.t('confidence_levels_chart_description') }, legend: { display: false } }
            }
        });
    }

    // -- EXPORTAR RESULTADOS --
    async function exportResults() {
        try {
            // Detecta idioma actual desde i18next
            const lang = i18next.language;
            const response = await fetch(`/api/export?lang=${lang}`);
            if (!response.ok) {
                //throw new Error('No hay resultados para exportar');
                throw new Error(i18next.t('no_results_to_export'));
            }

            // Obtener el nombre real del archivo desde el header Content-Disposition
            const disposition = response.headers.get("Content-Disposition");
            let filename = "Resultados_sesion.csv"; // fallback
            if (disposition && disposition.includes("filename=")) {
                filename = disposition.split("filename=")[1].replace(/["']/g, "");
            }

            // Descargar CSV
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;   // El nombre viene del servidor
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);

            //showNotification(`✅ Resultados exportados como ${filename}`, 'success');
            showNotification(i18next.t('export_success', { filename: filename }), 'success');
        } catch (error) {
            console.error('Error exportando:', error);
            //showNotification('❌ Error al exportar resultados', 'error');
            showNotification(i18next.t('export_error'), 'error');
        }
    }

    // -- LIMPIAR SESIÓN --
    function clearSession() {
        //if (!confirm('¿Estás seguro de que quieres limpiar la sesión actual?')) return;
        if (!confirm(i18next.t('clear_session_confirm'))) return;

        // Limpiar estadísticas
        sessionStats = {
            totalProcessed: 0,
            confidenceSum: 0,
            classCount: {},
            confidenceLevels: []
        };
        
        // Limpiar resultados guardados para exportar
        sessionResults = [];

        // Borrar también del localStorage
        localStorage.removeItem('sessionStats');

        updateStatsDisplay();

        // Deshabilitar botón de exportación
        if (exportBtn) exportBtn.disabled = true;

        // Limpiar backend
        fetch('/api/clear_session', { method: 'POST' })
            .then(res => res.json())
            .then(data => console.log(data.message))
            .catch(err => console.error('Error limpiando sesión en backend:', err));

        // Limpiar resultados y volver a cargar pantalla inicial desde Flask
        fetch('/')
            .then(response => response.text())
            .then(html => {
                // Crear un DOM temporal
                const parser = new DOMParser();
                const doc = parser.parseFromString(html, 'text/html');

                // Actualizar resultsGrid
                const newResultsGrid = doc.querySelector('#results-grid');
                if (newResultsGrid && resultsGrid) {
                    resultsGrid.innerHTML = newResultsGrid.innerHTML;

                    // Reaplicar traducciones al nuevo contenido
                    updateContent();
                }

                // Resetear el área de estado
                const loader = document.getElementById('loader');
                const progressText = document.getElementById('progress-text');
                if (loader) loader.style.display = 'none';
                //if (progressText) progressText.textContent = 'Listo para análisis';
                if (progressText) progressText.textContent = i18next.t('status_ready');

                //showNotification('🧹 Sesión limpiada', 'info');
                showNotification(i18next.t('session_cleared'), 'info');
            })
            .catch(err => {
                console.error('Error recargando pantalla inicial:', err);
                //showNotification('❌ No se pudo recargar la pantalla inicial', 'error');
                showNotification(i18next.t('clear_session_error'), 'error');
            });
    }

    // Event listeners para nuevas funcionalidades
    toggleStatsBtn?.addEventListener('click', showStatsModal);
    closeStatsModal?.addEventListener('click', () => statsModal.style.display = 'none');
    exportBtn?.addEventListener('click', exportResults);
    clearSessionBtn?.addEventListener('click', clearSession);
    
    // Event listeners para cámara
    startCameraBtn?.addEventListener('click', initCamera);
    stopCameraBtn?.addEventListener('click', stopCamera);
    capturePhotoBtn?.addEventListener('click', capturePhoto);
    switchCameraBtn?.addEventListener('click', switchCamera);
    
    // Detener cámara al cerrar la página
    window.addEventListener('beforeunload', () => {
        if (currentStream) {
            stopCamera();
        }
    });
});