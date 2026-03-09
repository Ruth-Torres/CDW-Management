import os
import sys

# Colores ANSI 
VERDE = "\033[92m" 
AZUL = "\033[94m" 
AMARILLO = "\033[93m" 
ROJO = "\033[91m"
CIAN = "\033[96m"
RESET = "\033[0m"

# --- Importar librerías de Python / PyTorch ---
from flask import Flask, request, jsonify, render_template, send_from_directory
from werkzeug.utils import secure_filename
from PIL import Image
import torch
import torch.nn as nn
from torchvision import transforms
from torchvision.models import resnet50
from datetime import datetime, timedelta
import json
from collections import defaultdict
import csv
import io

# --- Configuración Inicial ---
# Usar ruta absoluta para evitar problemas
# Aquí se definen las carpetas donde se guardarán imágenes subidas
# y las salidas de Grad-CAM, además de los formatos de archivo permitidos.
# BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
# GRADCAM_FOLDER = os.path.join(BASE_DIR, 'gradcam_outputs')

# ========================
# RUTAS ABSOLUTAS PARA PORTABLE
# ========================
if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS  # Si es .exe generado por PyInstaller
    print(f"{AZUL}[INFO]{RESET} Modo EXE detectado. BASE_DIR = {VERDE}{BASE_DIR}{RESET}")
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    print(f"{AZUL}[INFO]{RESET} Modo script .py. BASE_DIR = {VERDE}{BASE_DIR}{RESET}")

UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
GRADCAM_FOLDER = os.path.join(BASE_DIR, 'gradcam_outputs')
TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates')
STATIC_DIR = os.path.join(BASE_DIR, 'static')
MODEL_PATH = os.path.join(BASE_DIR, 'best_resnet_multilabel_v5.pt')
print(f"{AZUL}[INFO]{RESET} Modelo en: {VERDE}{MODEL_PATH}{RESET}")

# Traducciones
LOCALES_DIR = os.path.join(STATIC_DIR, 'locales')
TRANSLATIONS_PATH = os.path.join(LOCALES_DIR, 'translations.json')
TRANSLATIONS_FILES = {
    'en': os.path.join(LOCALES_DIR, 'en.json'),
    'es': os.path.join(LOCALES_DIR, 'es.json'),
    'fr': os.path.join(LOCALES_DIR, 'fr.json'),
}
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp', 'tiff', 'webp'}

app = Flask(__name__, template_folder=TEMPLATES_DIR, static_folder=STATIC_DIR)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['GRADCAM_FOLDER'] = GRADCAM_FOLDER
app.config['MAX_CONTENT_LENGTH'] = None  # Sin límite de tamaño

# Crear la carpeta de subidas si no existe
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
print(f"{AZUL}[INFO]{RESET} Carpeta de uploads: {VERDE}{UPLOAD_FOLDER}{RESET}")

# Crear la carpeta de Grad-CAM si no existe
os.makedirs(GRADCAM_FOLDER, exist_ok=True)
print(f"{AZUL}[INFO]{RESET} Carpeta de gradcam_outputs: {VERDE}{GRADCAM_FOLDER}{RESET}")

# --- Definiciones del Modelo ---
# Estas estructuras sirven para mapear nombres de clases a emojis,
# colores y etiquetas legibles para el usuario.
# ⚠️ IMPORTANTE: el orden de CLASS_NAMES debe coincidir con el entrenamiento del modelo.
CLASS_NAMES = ['hormigon', 'ceramico', 'piedra', 'yeso', 'asfaltico', 'basura_general']

CLASS_EMOJIS = {
    'hormigon': '🏗️', 'ceramico': '🧱', 'piedra': '🏛️', 'yeso': '🎨', 'asfaltico': '🛣️', 'basura_general': '🗑️' 
}

CLASS_DISPLAY_NAMES = {
    'hormigon': 'Hormigón',
    'ceramico': 'Cerámico',
    'piedra': 'Piedra',
    'yeso': 'Yeso',
    'asfaltico': 'Asfáltico',
    'basura_general': 'Basura General'
}

CLASS_COLORS = {
    'hormigon': '#7f8c8d',       # gris hormigón
    'ceramico': '#d35400',       # naranja cerámico
    'piedra': '#8e44ad',         # morado piedra
    'yeso': '#f39c12',           # amarillo yeso
    'asfaltico': '#34495e',      # gris oscuro asfáltico
    'basura_general': '#e74c3c'  # rojo basura
}

# --- Carga del Modelo ---
# Se usan variables globales para mantener cargado el modelo, el dispositivo
# (CPU o GPU) y las transformaciones de preprocesamiento de imágenes.
model = None
device = None
transform = None

def load_model():
    """Carga el modelo ResNet50 pre-entrenado una sola vez."""
    # Intenta cargar desde la carpeta actual o la carpeta padre.
    # Reemplaza la capa fully-connected para clasificación multiclase.
    global model, device, transform
    
    try:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # Buscar el modelo en la carpeta padre o en la carpeta actual
        nombre_archivo = "best_resnet_multilabel_v5.pt"
        model_path = os.path.join(BASE_DIR, nombre_archivo)
        if not os.path.exists(model_path):
            model_path = os.path.join(os.path.dirname(BASE_DIR), nombre_archivo)

        if not os.path.exists(model_path):
            raise FileNotFoundError( f"{ROJO}[ERROR]{RESET} No se encontró el archivo {AMARILLO}{nombre_archivo}{RESET} en {AMARILLO}{model_path}{RESET}" )

        # Cargar modelo
        model = resnet50(weights=None)
        num_features = model.fc.in_features
        model.fc = nn.Sequential(
            nn.Linear(num_features, len(CLASS_NAMES)),
            nn.Sigmoid()  # salida en [0,1] para probabilidades
        )
        
        # Cargar pesos entrenados
        model.load_state_dict(torch.load(model_path, map_location=device))
        model = model.to(device)
        model.eval()
        
        # Transformaciones estándar de ResNet (224x224 + normalización)
        transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])
        
        print(f"{AZUL}[INFO]{RESET} Modelo cargado exitosamente desde {VERDE}{model_path}{RESET} en {VERDE}{device}{RESET}")
        
    except Exception as e:
        print(f"{ROJO}[ERROR]{RESET} Error cargando el modelo: {ROJO}{e}{RESET}")
        raise

def predict_image(image_path):
    """Realiza una predicción sobre una única imagen."""
    # Devuelve:
    #   - predicted_class: nombre crudo de la clase más probable
    #   - confidence: probabilidad de la clase ganadora (0–100%)
    #   - detailed_probs: lista de todas las clases con sus probabilidades, ordenadas descendientemente
    if not model:
        raise RuntimeError(f"{ROJO}[ERROR]{RESET} El modelo no está cargado.")

    try:
        start_time = datetime.now()
        print(f"{CIAN}[TRACE]{RESET} Prediciendo imagen: {VERDE}{image_path}{RESET}")
        
        # Verificar que el archivo existe antes de abrirlo
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"{ROJO}[ERROR]{RESET} No se encontró la imagen: {AMARILLO}{image_path}{RESET}")
        
        image = Image.open(image_path).convert('RGB')
        img_t = transform(image).unsqueeze(0).to(device)

        with torch.no_grad():
            output = model(img_t)
            probabilities = output
            
            # Obtener todas las probabilidades como array de numpy
            all_probs = probabilities[0].cpu().numpy()
            
            # Obtener la mejor predicción
            confidence, pred_index = torch.max(probabilities, 1)
            
            predicted_class = CLASS_NAMES[pred_index.item()]
            confidence_percent = confidence.item() * 100
            
            # Calcular tiempo de procesamiento
            processing_time = (datetime.now() - start_time).total_seconds()
            
            # Preparar todas las probabilidades para el frontend
            detailed_probs = []
            for i, prob in enumerate(all_probs):
                detailed_probs.append({
                    'class_name': CLASS_NAMES[i],  # identificador crudo
                    'display_name': CLASS_DISPLAY_NAMES.get(CLASS_NAMES[i], CLASS_NAMES[i].capitalize()),  # nombre bonito
                    'probability': float(prob) * 100
                })
            
            # Ordenar por probabilidad descendente
            detailed_probs.sort(key=lambda x: x['probability'], reverse=True)
            
            # Actualizar estadísticas
            update_stats(predicted_class, confidence_percent, processing_time)
            
            print(f"{AZUL}[INFO]{RESET} Predicción exitosa: {VERDE}{predicted_class}{RESET} ({AMARILLO}{confidence_percent:.1f}%{RESET}) - Tiempo: {AMARILLO}{processing_time:.2f}s{RESET}")
            return predicted_class, confidence_percent, detailed_probs

    except Exception as e:
        print(f"{ROJO}[ERROR]{RESET} Error prediciendo la imagen {AMARILLO}{image_path}{RESET}: {ROJO}{e}{RESET}")
        return None, None, None

def allowed_file(filename):
    """Verifica si la extensión del archivo es permitida."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def clean_uploads_folder():
    """Elimina todos los archivos de la carpeta uploads."""
    # Usado antes de nuevas clasificaciones para no acumular basura.
    try:
        if os.path.exists(UPLOAD_FOLDER):
            for filename in os.listdir(UPLOAD_FOLDER):
                file_path = os.path.join(UPLOAD_FOLDER, filename)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                        print(f"{AZUL}[INFO]{RESET} Archivo eliminado: {VERDE}{filename}{RESET}")
                except Exception as e:
                    print(f"{ROJO}[ERROR]{RESET} Error eliminando archivo {AMARILLO}{filename}{RESET}: {ROJO}{e}{RESET}")
            print(f"{AZUL}[INFO]{RESET} Limpieza de carpeta uploads completada")
        else:
            print(f"{AMARILLO}[WARNING]{RESET} La carpeta uploads no existe")
    except Exception as e:
        print(f"{ROJO}[ERROR]{RESET} Error durante la limpieza de uploads: {ROJO}{e}{RESET}")

def clean_gradcam_folder():
    """Elimina todos los archivos de la carpeta gradcam_outputs."""
    # Similar a clean_uploads_folder pero para Grad-CAM.
    try:
        if os.path.exists(GRADCAM_FOLDER):
            for filename in os.listdir(GRADCAM_FOLDER):
                file_path = os.path.join(GRADCAM_FOLDER, filename)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                        print(f"{AZUL}[INFO]{RESET} Archivo eliminado: {VERDE}{filename}{RESET}")
                except Exception as e:
                    print(f"{ROJO}[ERROR]{RESET} Error eliminando archivo {AMARILLO}{filename}{RESET}: {ROJO}{e}{RESET}")
            print(f"{AZUL}[INFO]{RESET} Limpieza de carpeta gradcam_outputs completada")
        else:
            print(f"{AMARILLO}[WARNING]{RESET} La carpeta gradcam_outputs no existe")
    except Exception as e:
        print(f"{ROJO}[ERROR]{RESET} Error durante la limpieza de gradcam_outputs: {ROJO}{e}{RESET}")

def clean_old_files(hours=24):
    """Elimina archivos más antiguos que el número de horas especificado."""
    # Se ejecuta al inicio del servidor como medida de mantenimiento.
    folders_to_clean = [UPLOAD_FOLDER, GRADCAM_FOLDER]

    current_time = datetime.now()
    cutoff_time = current_time - timedelta(hours=hours)

    for folder in folders_to_clean:
        try:
            if not os.path.exists(folder):
                continue
            
            for filename in os.listdir(folder):
                file_path = os.path.join(folder, filename)
                try:
                    if os.path.isfile(file_path):
                        file_time = datetime.fromtimestamp(os.path.getctime(file_path))
                        if file_time < cutoff_time:
                            os.unlink(file_path)
                            print(f"Archivo antiguo eliminado en {folder}: {filename}")
                except Exception as e:
                    print(f"Error eliminando archivo antiguo {filename} en {folder}: {e}")
        except Exception as e:
            print(f"Error accediendo a la carpeta {folder}: {e}")

# --- Estadísticas del Sistema ---
# Estas métricas son útiles para el monitoreo del rendimiento y uso de la app.
# Se almacenan en memoria y se reinician si el servidor se reinicia.
# Variables globales para estadísticas
stats = {
    'total_images_processed': 0,
    'predictions_by_class': defaultdict(int),  # conteo de predicciones por clase
    'confidence_levels': [],                   # últimas confianzas registradas
    'processing_times': [],                    # últimos tiempos de predicción
    'daily_usage': defaultdict(int),           # número de imágenes por día
    'last_reset': datetime.now().strftime('%Y-%m-%d')
}

def update_stats(predicted_class, confidence, processing_time):
    """Actualiza las estadísticas del sistema."""
    global stats
    
    # Verificar si es un nuevo día → reinicia daily_usage
    today = datetime.now().strftime('%Y-%m-%d')
    if today != stats['last_reset']:
        stats['daily_usage'] = defaultdict(int)
        stats['last_reset'] = today
    
    stats['total_images_processed'] += 1
    stats['predictions_by_class'][predicted_class] += 1
    stats['confidence_levels'].append(confidence)
    stats['processing_times'].append(processing_time)
    stats['daily_usage'][today] += 1
    
    # Mantener solo los últimos 100 registros para evitar consumo excesivo de memoria
    if len(stats['confidence_levels']) > 100:
        stats['confidence_levels'] = stats['confidence_levels'][-100:]
    if len(stats['processing_times']) > 100:
        stats['processing_times'] = stats['processing_times'][-100:]

def get_stats_summary():
    """Genera un resumen de estadísticas."""
    # Devuelve información agregada: promedio de confianza, tiempos, clase más común, etc.
    if stats['total_images_processed'] == 0:
        return {
            'total_processed': 0,
            'avg_confidence': 0,
            'avg_processing_time': 0,
            'most_common_class': 'N/A',
            'daily_count': 0
        }
    
    today = datetime.now().strftime('%Y-%m-%d')
    most_common = max(stats['predictions_by_class'].items(), key=lambda x: x[1]) if stats['predictions_by_class'] else ('N/A', 0)
    
    return {
        'total_processed': stats['total_images_processed'],
        'avg_confidence': round(sum(stats['confidence_levels']) / len(stats['confidence_levels']), 1) if stats['confidence_levels'] else 0,
        'avg_processing_time': round(sum(stats['processing_times']) / len(stats['processing_times']), 2) if stats['processing_times'] else 0,
        'most_common_class': CLASS_DISPLAY_NAMES.get(most_common[0], most_common[0].capitalize()),
        'most_common_count': most_common[1],
        'daily_count': stats['daily_usage'][today],
        'class_distribution': dict(stats['predictions_by_class'])
    }

# --- Exportación de Resultados ---
# Los resultados solo corresponden a la sesión actual (no se guardan en BD ni disco).
# Se exportan a CSV en memoria (StringIO) para descarga directa desde el frontend.
session_results = []

def save_session_result(result_data):
    """Guarda los resultados de la sesión actual."""
    # Guarda resultados en memoria, no persistentes.
    global session_results
    session_results.append({
        'timestamp': result_data['timestamp'],
        'filename': result_data['filename'],
        'predicted_class': result_data['predicted_class'],
        'confidence': result_data['confidence'],
        'probabilities': json.dumps(result_data['probabilities'])
    })

def export_results_csv(lang='es'):
    """Exporta los resultados de la sesión a CSV con cabeceras legibles y acentos correctos (UTF-8 BOM)."""
    # Genera CSV en memoria → útil para exportación rápida desde frontend.
    if not session_results:
        return None
    
    output = io.StringIO()
    # Escribir BOM para compatibilidad con Excel
    output.write('\ufeff')  
    
    # Obtener traducciones según idioma
    t = TRANSLATIONS.get(lang, TRANSLATIONS['es'])
    
    writer = csv.DictWriter(
        output,
        fieldnames=[t['Timestamp'], t['Nombre del archivo'], t['Material'], t['Probabilidad'], t['Top 3 de probabilidades (>50%)']],
        delimiter=';'
    )
    writer.writeheader()
    
    for result in session_results:
        # Filtrar top 3 probabilidades mayores a 50%
        probs = [p for p in json.loads(result['probabilities']) if p['probability'] > 50][:3]
        top_3 = '; '.join([
            f"{t.get(p['class_name'], p['class_name'].capitalize())}: {p['probability']:.1f}%"
            for p in probs
        ])
        
        writer.writerow({
            t['Timestamp']: result['timestamp'],
            t['Nombre del archivo']: result['filename'],
            t['Material']: t.get(result['predicted_class'], result['predicted_class'].capitalize()),
            t['Probabilidad']: f"{result['confidence']:.1f}%",
            t['Top 3 de probabilidades (>50%)']: top_3
        })
    
    output.seek(0)
    return output.getvalue()


# --- Manejo de Errores ---
@app.errorhandler(500)
def internal_error(e):
    return jsonify({'error': 'Error interno del servidor. Revise los logs.'}), 500

# --- Rutas de la Aplicación ---
# Endpoints principales:
# - / : Renderiza la página principal
# - /classify : Clasifica imágenes subidas
# - /uploads/<filename> : Sirve imágenes subidas
# - /cleanup : Limpieza manual de uploads y gradcam_outputs
# - /api/* : Endpoints JSON para stats, exportación, health, etc.
# - /classify/camera : Flujo optimizado para cámaras en tiempo real
# - /api/gradcam : Generación de Grad-CAM

# Cargar traducciones
with open(TRANSLATIONS_PATH, "r", encoding="utf-8") as f:
    TRANSLATIONS = json.load(f)

@app.route('/')
def index():
    """Renderiza la página principal."""
    device_name = "CUDA" if device and device.type == "cuda" else "CPU"
    return render_template('index.html', 
                         class_names=CLASS_NAMES, 
                         class_emojis=CLASS_EMOJIS,
                         device_type=device_name)

@app.route('/classify', methods=['POST'])
def classify_images():
    """Endpoint para clasificar las imágenes subidas."""
    # Flujo general del endpoint:
    # 1. Limpia la carpeta de uploads (para no acumular archivos viejos).
    # 2. Recibe múltiples archivos desde el cliente (POST con 'files').
    # 3. Verifica formato y guarda con un nombre seguro + timestamp.
    # 4. Corre la predicción para cada imagen.
    # 5. Devuelve resultados en JSON y los guarda en la sesión para exportación.
    try:
        print("=== Iniciando clasificación ===")
        
        # Limpiar archivos anteriores antes de procesar nuevos
        # print("Limpiando archivos anteriores...")
        # clean_uploads_folder()
        
        if 'files' not in request.files:
            return jsonify({'error': 'No se encontraron archivos en la solicitud'}), 400

        files = request.files.getlist('files')
        results = []

        if not files or files[0].filename == '':
            return jsonify({'error': 'No se seleccionaron archivos'}), 400

        print(f"{AZUL}[INFO]{RESET} Procesando {AMARILLO}{len(files)}{RESET} archivos")

        for i, file in enumerate(files):
            print(f"{CIAN}[TRACE]{RESET} Procesando archivo {AMARILLO}{i+1}/{len(files)}{RESET}: {VERDE}{file.filename}{RESET}")
            
            if file and allowed_file(file.filename):
                try:
                    # Limpiar y asegurar el nombre del archivo
                    filename = secure_filename(file.filename)
                    if not filename:
                        filename = f"image_{i+1}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                    
                    # Agregar timestamp para evitar conflictos
                    name, ext = os.path.splitext(filename)
                    filename = f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
                    
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    
                    # Asegurar que la carpeta existe
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    
                    print(f"{CIAN}[TRACE]{RESET} Guardando en: {VERDE}{filepath}{RESET}")
                    
                    # Guardar archivo con manejo de errores mejorado
                    try:
                        file.save(filepath)
                    except Exception as save_error:
                        print(f"{ROJO}[ERROR]{RESET} Error guardando archivo: {ROJO}{save_error}{RESET}")
                        # Reintentar con un nombre diferente
                        filename = f"backup_{i}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                        file.save(filepath)
                    
                    # Verificar que se guardó correctamente con reintentos
                    retries = 3
                    while retries > 0 and not os.path.exists(filepath):
                        print(f"{AMARILLO}[WARNING]{RESET} Archivo no encontrado, reintentando... ({AMARILLO}{retries}{RESET} intentos restantes)")
                        file.save(filepath)
                        retries -= 1
                    
                    if not os.path.exists(filepath):
                        print(f"{ROJO}[ERROR]{RESET} El archivo no se guardó correctamente después de varios intentos: {AMARILLO}{filepath}{RESET}")
                        continue
                    
                    # Realizar predicción
                    pred_class, confidence, detailed_probs = predict_image(filepath)

                    if pred_class is not None:
                        result_data = {
                            'filename': filename,
                            'image_url': f'/uploads/{filename}',
                            'predicted_class': pred_class,
                            'display_name': CLASS_DISPLAY_NAMES.get(pred_class, pred_class.capitalize()),
                            'confidence': confidence,
                            'emoji': CLASS_EMOJIS.get(pred_class, '📦'),
                            'color': CLASS_COLORS.get(pred_class, '#34495e'),
                            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            'probabilities': detailed_probs
                        }
                        
                        results.append(result_data)
                        # Guardar resultado en la sesión para exportación
                        save_session_result(result_data)
                        print(f"{CIAN}[TRACE]{RESET} Archivo procesado exitosamente: {VERDE}{filename}{RESET}")
                    else:
                        print(f"{ROJO}[ERROR]{RESET} Error en la predicción de {AMARILLO}{filename}{RESET}")
                        
                except Exception as file_error:
                    print(f"{ROJO}[ERROR]{RESET} Error procesando archivo {AMARILLO}{file.filename}{RESET}: {ROJO}{file_error}{RESET}")
                    continue
            else:
                print(f"{AMARILLO}[WARNING]{RESET} Archivo no permitido o inválido: {AMARILLO}{file.filename}{RESET}")

        print(f"=== Clasificación completada: {len(results)} resultados ===")
        
        if len(results) == 0:
            return jsonify({'error': 'No se pudieron procesar las imágenes. Verifica que sean archivos de imagen válidos.'}), 400
            
        return jsonify({'results': results})
        
    except Exception as e:
        print(f"{ROJO}[ERROR]{RESET} Error general en clasificación: {ROJO}{e}{RESET}")
        return jsonify({'error': f'Error interno del servidor. Detalles: {str(e)}'}), 500

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Sirve los archivos subidos para que se puedan mostrar en el HTML."""
    try:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if not os.path.exists(filepath):
            print(f"{ROJO}[ERROR]{RESET} Archivo no encontrado: {AMARILLO}{filepath}{RESET}")
            return jsonify({'error': 'Archivo no encontrado'}), 404
        
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    except Exception as e:
        print(f"{ROJO}[ERROR]{RESET} Error sirviendo archivo {AMARILLO}{filename}{RESET}: {ROJO}{e}{RESET}")
        return jsonify({'error': 'Error sirviendo archivo'}), 500

@app.route('/cleanup', methods=['POST'])
def manual_cleanup():
    """Endpoint para limpiar manualmente las carpetas uploads y gradcam_outputs."""
    try:
        clean_uploads_folder()
        clean_gradcam_folder()
        return jsonify({'message': 'Carpetas uploads y gradcam_outputs limpiadas exitosamente'}), 200
    except Exception as e:
        print(f"{ROJO}[ERROR]{RESET} Error en limpieza manual: {ROJO}{e}{RESET}")
        return jsonify({'error': f'Error limpiando uploads o gradcam_outputs: {str(e)}'}), 500

@app.route('/api/stats')
def get_api_statistics():
    """API para obtener estadísticas del sistema."""
    try:
        stats_summary = get_stats_summary()
        return jsonify(stats_summary), 200
    except Exception as e:
        print(f"{ROJO}[ERROR]{RESET} Error obteniendo estadísticas: {ROJO}{e}{RESET}")
        return jsonify({'error': 'Error obteniendo estadísticas'}), 500

@app.route('/api/export', methods=['GET'])
def export_session_results():
    """API para exportar resultados de la sesión actual."""
    try:
        # Obtener idioma desde frontend
        lang = request.args.get('lang', 'es')
        csv_data = export_results_csv(lang=lang)
        if not csv_data:
            return jsonify({'error': 'No hay resultados para exportar'}), 404
        
        t = TRANSLATIONS.get(lang, TRANSLATIONS['es'])
        filename = f"{t['session_results_filename']}_{datetime.now().strftime('%Y%m%d__%H%M%S')}.csv"
        
        response = app.response_class(
            csv_data,
            mimetype='text/csv; charset=utf-8',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )
        return response
    except Exception as e:
        print(f"{ROJO}[ERROR]{RESET} Error exportando resultados: {ROJO}{e}{RESET}")
        return jsonify({'error': 'Error exportando resultados'}), 500

@app.route('/api/clear_session', methods=['POST'])
def clear_session_api():
    """Limpia los resultados de la sesión actual en el backend."""
    global session_results
    session_results = []
    return jsonify({'message': 'Sesión limpiada correctamente en el servidor'}), 200

@app.route('/classify/camera', methods=['POST'])
def classify_camera_frame():
    """Endpoint optimizado para clasificar frames de cámara en tiempo real."""
    try:
        if 'files' not in request.files:
            return jsonify({'error': 'No se encontraron archivos'}), 400

        file = request.files['files']
        
        if file and file.filename != '':
            try:
                # Leer imagen desde memoria
                image_data = file.read()
                image = Image.open(io.BytesIO(image_data)).convert('RGB')
                
                if not transform:
                    return jsonify({'error': 'Modelo no cargado'}), 500
                
                img_t = transform(image).unsqueeze(0).to(device)
                
                with torch.no_grad():
                    output = model(img_t)   # salida ya está en [0,1] por Sigmoid
                    all_probs = output[0].cpu().numpy()
                    
                    # Escoger clase con mayor probabilidad
                    pred_index = int(all_probs.argmax())
                    confidence = float(all_probs[pred_index]) * 100
                    predicted_class = CLASS_NAMES[pred_index]
                    
                    result = {
                        'predicted_class': predicted_class,
                        'display_name': CLASS_DISPLAY_NAMES.get(predicted_class, predicted_class.capitalize()),
                        'confidence': confidence,
                        'emoji': CLASS_EMOJIS.get(predicted_class, '📦'),
                        'color': CLASS_COLORS.get(predicted_class, '#34495e'),
                        'timestamp': datetime.now().strftime("%H:%M:%S")
                    }
                    
                    return jsonify({'result': result})
                    
            except Exception as e:
                print(f"{ROJO}[ERROR]{RESET} Error procesando frame de cámara: {ROJO}{e}{RESET}")
                return jsonify({'error': 'Error procesando imagen'}), 500
        
        return jsonify({'error': 'Archivo inválido'}), 400
        
    except Exception as e:
        print(f"{ROJO}[ERROR]{RESET} Error en endpoint de cámara: {ROJO}{e}{RESET}")
        return jsonify({'error': 'Error interno del servidor'}), 500

@app.route('/api/health')
def health_check():
    """API para verificar el estado del sistema."""
    try:
        model_status = "OK" if model is not None else "ERROR"
        device_status = str(device) if device is not None else "N/A"
        
        return jsonify({
            'status': 'healthy',
            'model_loaded': model_status,
            'device': device_status,
            'upload_folder': UPLOAD_FOLDER,
            'supported_formats': list(ALLOWED_EXTENSIONS),
            'timestamp': datetime.now().isoformat()
        }), 200
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

@app.route('/api/gradcam', methods=['POST'])
def generate_gradcam():
    """Genera y devuelve el heatmap Grad-CAM de una imagen procesada."""
    try:
        data = request.get_json()
        if not data or 'filename' not in data:
            return jsonify({'error': 'No se proporcionó el nombre de archivo'}), 400

        filename = data['filename']
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        if not os.path.exists(filepath):
            return jsonify({'error': 'Archivo no encontrado'}), 404

        # Carpeta de salida
        gradcam_folder = os.path.join(BASE_DIR, 'gradcam_outputs')
        os.makedirs(gradcam_folder, exist_ok=True)

        # Generar Grad-CAM para la clase más probable
        from gradcam_module import generate_gradcam_image
        gradcam_urls = generate_gradcam_image(image_path=filepath, filename=filename, model=model, device=device, class_names=CLASS_NAMES, output_folder=gradcam_folder, threshold=0.5)

        return jsonify({'heatmap_urls': gradcam_urls}), 200

    except Exception as e:
        print(f"{ROJO}[ERROR]{RESET} Error generando Grad-CAM: {ROJO}{e}{RESET}")
        return jsonify({'error': 'Error generando Grad-CAM'}), 500

@app.route('/gradcam_outputs/<filename>')
def serve_gradcam(filename):
    """Sirve los heatmaps Grad-CAM generados."""
    gradcam_folder = os.path.join(BASE_DIR, 'gradcam_outputs')
    return send_from_directory(gradcam_folder, filename)

# --- Arranque de la Aplicación ---
if __name__ == '__main__':
    try:
        load_model()  # Cargar el modelo al iniciar
        
        # Limpiar archivos antiguos al iniciar (opcional)
        # print("Limpiando archivos antiguos al iniciar servidor...")
        # clean_uploads_folder()        # Limpia uploads
        # clean_gradcam_folder()        # Limpia gradcam_outputs
        # clean_old_files(hours=24)     # Elimina archivos de más de 24 horas
        
        print(f"{VERDE}[INFO]{RESET} Servidor iniciado.")
        app.run(debug=False, host='127.0.0.1', port=5000)
    except Exception as e:
        print(f"{ROJO}[ERROR]{RESET} Error iniciando la aplicación: {ROJO}{e}{RESET}")