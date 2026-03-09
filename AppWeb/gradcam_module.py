import torch
import numpy as np
import cv2
from PIL import Image
from torchvision import transforms
import os

# --------------------------
# Transformaciones de imagen
# --------------------------
transform = transforms.Compose([
    transforms.Resize((224, 224)),      # Redimensiona la imagen al tamaño esperado por la red
    transforms.ToTensor(),              # Convierte la imagen a un tensor [C,H,W] con valores 0-1
    transforms.Normalize(mean=[0.485, 0.456, 0.406],    # Normalización según ImageNet
                         std=[0.229, 0.224, 0.225])
])

# --------------------------
# Función para desactivar ReLU inplace
# --------------------------
# En muchos modelos (por ejemplo ResNet), las capas ReLU se definen con inplace=True.
# Esto significa que la operación ReLU modifica directamente el tensor de entrada, sobrescribiendo sus valores en memoria.
#
# Para entrenamiento normal esto suele ser correcto y ahorra memoria, pero para Grad-CAM puede causar problemas porque:
# - Grad-CAM necesita conservar las activaciones originales de la capa convolucional
# - y también necesita calcular gradientes respecto a esas activaciones.
#
# Las operaciones inplace pueden:
# - sobrescribir valores que PyTorch necesita para el backward
# - provocar errores del tipo:
#   "one of the variables needed for gradient computation has been modified by an inplace operation"
# - o generar gradientes incorrectos.
#
# Por eso, antes de usar Grad-CAM, desactivamos el comportamiento inplace de todas las capas ReLU del modelo.
def set_relu_inplace(module):
    """
    Recorre recursivamente todas las subcapas del modelo (la red) y establece inplace=False en todas las ReLU.
    
    Parámetro:
    - module: módulo raíz (por ejemplo el modelo completo o un submódulo).
    """
    # module.children() devuelve un iterador sobre las subcapas directas del módulo.
    # En un modelo como ResNet, esto incluye bloques convolucionales, capas secuenciales, etc.
    for child in module.children():
        # Comprobamos si la subcapa es una ReLU
        if isinstance(child, torch.nn.ReLU):

            # Desactivamos la operación inplace.
            # A partir de ahora, la ReLU:
            # - no sobrescribe el tensor de entrada
            # - crea un nuevo tensor de salida
            #
            # Esto garantiza que:
            # - las activaciones se conserven correctamente
            # - el grafo de gradientes de PyTorch no se rompa
            # - Grad-CAM pueda calcular correctamente ∂(output)/∂(activaciones)
            child.inplace = False
        else:
            # Si la subcapa NO es una ReLU, puede ser:
            # - un bloque convolucional
            # - un bloque residual
            # - un nn.Sequential
            #
            # Llamamos recursivamente a esta función para seguir
            # explorando la red en profundidad hasta encontrar ReLU.
            set_relu_inplace(child)

# --------------------------
# Función principal Grad-CAM
# --------------------------
def generate_gradcam_image(image_path, filename, model, device, class_names, output_folder, threshold=0.5):
    """
    Genera y guarda heatmaps Grad-CAM para las clases cuya probabilidad supera el umbral (50%).
    """
    os.makedirs(output_folder, exist_ok=True)   # Crea carpeta de salida si no existe
    set_relu_inplace(model)                     # Asegura que ReLU no sobrescriba activaciones

    # Variables donde se almacenarán gradientes y activaciones de la capa target
    gradients = None
    activations = None

    # --------------------------
    # Hook de backward
    # --------------------------
    # Definimos una función que será usada como backward hook.
    # Un backward hook es una función que PyTorch llama automáticamente durante el backward pass, justo cuando se calculan los gradientes de una capa concreta.
    # Este hook se utiliza para capturar los gradientes de la salida de la clase objetivo respecto a las activaciones (feature maps Aᵏ) de la capa convolucional target.
    def save_gradient(module, grad_input, grad_output):
        """
        Hook que se ejecuta durante el backward pass.
        
        Parámetros que PyTorch pasa automáticamente:
        - module: la capa donde se ha registrado el hook (por ejemplo, la capa convolucional target).
        - grad_input: tupla con los gradientes que entran a la capa (∂L/∂input).
                    No se usa en Grad-CAM.
        - grad_output: tupla con los gradientes que salen de la capa (∂L/∂output).
                    grad_output[0] contiene el tensor clave para Grad-CAM.
        
        En Grad-CAM, grad_output[0] representa:

        grad_output[0] = ∂yᶜ / ∂Aᵏ

        donde:
        - yᶜ es la salida de la clase objetivo
        - Aᵏ es el feature map k de la capa convolucional target

        Respresenta cómo cambia la salida de la clase objetivo respecto a las activaciones de la capa convolucional.
        Almacenar este tensor es crucial porque lo usaremos para calcular los pesos αₖ, que indican la importancia de cada canal en la capa convolucional para la clase objetivo.
        """
        # Indicamos que vamos a modificar la variable 'gradients' definida en el scope exterior (fuera de esta función). 
        # Sin 'nonlocal', esta asignación crearía una variable local.
        nonlocal gradients

        # grad_output es una tupla; grad_output[0] es el tensor real de gradientes.
        # Su forma es: [batch_size, C, H, W]
        # - batch_size: normalmente 1
        # - C: número de canales de la capa convolucional. Cada canal k contiene el gradiente ∂yᶜ / ∂Aᵏ
        # - H, W: dimensiones espaciales del mapa de activación
        #
        # Cada valor indica cuánto cambiaría la salida de la clase objetivo si se modifica ligeramente esa activación concreta.
        # Este tensor se guarda para calcular posteriormente los pesos αₖ (pooled gradients).
        gradients = grad_output[0]  # Guardamos los gradientes
    
    # --------------------------
    # Hook de forward
    # --------------------------
    # Definimos una función que será usada como forward hook.
    # Un forward hook es una función que PyTorch llama automáticamente durante el forward pass, justo cuando una capa concreta produce su salida.
    # Este hook se usa para capturar las activaciones (feature maps Aᵏ) de la capa convolucional target.
    def forward_hook(module, input, output):
        """
        Hook que se ejecuta durante el forward pass.

        Parámetros que PyTorch pasa automáticamente:
        - module: la capa donde se ha registrado el hook (por ejemplo, la capa convolucional target).
        - input: tupla con los tensores de entrada a la capa.
                No se usa directamente en Grad-CAM.
        - output: tensor de salida de la capa, es decir, las activaciones (feature maps).

        En Grad-CAM, 'output' corresponde a:
        output = {Aᵏ}, el conjunto de feature maps de la capa target.
        """
        # Indicamos que vamos a modificar la variable 'activations' definida en el scope exterior.
        # Sin 'nonlocal', esta asignación crearía una variable local dentro de la función.
        nonlocal activations

        # Guardamos las activaciones de la capa target.
        # La forma típica de este tensor es:
        # [batch_size, C, H, W]
        # - batch_size: normalmente 1
        # - C: número de canales (cada canal detecta un tipo de patrón). Cada canal k es un feature map Aᵏ
        # - H, W: dimensiones espaciales del mapa de activación. Cada Aᵏ es un mapa 2D que indica dónde la red detecta un patrón concreto
        #
        # Estas activaciones se usarán más adelante para:
        #   1) ponderarlas con los pesos αₖ obtenidos del backward
        #   2) combinarlas para generar el heatmap final de Grad-CAM
        activations = output

    # --------------------------
    # Selección de la última capa convolucional (ResNet50)
    # --------------------------
    # Elegimos la última capa convolucional del modelo.
    # En ResNet50:
    # - layer4 es el último bloque convolucional
    # - [-1] selecciona el último bloque residual dentro de layer4
    # - conv3 es la última convolución de ese bloque
    #
    # Esta capa es ideal para Grad-CAM porque:
    # - La más profunda del modelo. Las capas convolucionales más profundas capturan más conceptos semánticos.
    # - La que tiene mejor equilibrio entre: información semántica (qué objeto es) e información espacial (dónde está en la imagen).
    # - Tiene alto nivel semántico (detecta objetos o partes completas)
    # - Aún conserva estructura espacial [H, W], necesaria para el heatmap
    # - Es la capa recomendada en el paper original de Grad-CAM
    #
    # Por qué NO usar capas anteriores
    # - Capas tempranas → mucho detalle espacial, poco significado semántico
    # - Capas muy tardías (fully connected) → no tienen estructura espacial [H,W]
    # Grad-CAM necesita: 
    # - una capa convolucional
    # - con mapas espaciales [H,W]
    target_layer = model.layer4[-1].conv3   # Última convolucional antes del fully connected

    # Registramos un forward hook en la capa target.
    # Este hook se ejecuta automáticamente durante el forward pass del modelo.
    # Cada vez que el modelo haga un forward pass, PyTorch:
    #   1. ejecuta la capa target (target_layer)
    #   2. llama automáticamente a forward_hook(...)
    #   3. pasa como output las activaciones de esa capa
    # Sirve para capturar las activaciones (feature maps) Aᵏ de la capa target.
    # Estas activaciones indican "dónde" se detectan ciertos patrones en la imagen.
    # Forma típica: [1, C, H, W]
    target_layer.register_forward_hook(forward_hook)        # Captura activaciones

    # Registramos un backward hook completo en la capa target.
    # Este hook se ejecuta automáticamente durante el backward pass (output.backward()).
    # Durante el backward():
    #   1. PyTorch calcula los gradientes
    #   2. cuando llega a target_layer
    #   3. llama automáticamente a save_gradient(...)
    # Sirve para capturar los gradientes ∂(salida de la clase objetivo)/∂(activaciones Aᵏ).
    # Estos gradientes indican "qué tan importantes" son las activaciones de cada canal para una clase específica.
    # Forma típica: [1, C, H, W]
    target_layer.register_full_backward_hook(save_gradient) # Captura gradientes

    # Resumen conceptual del bloque completo: 
    # - Seleccionas la última capa convolucional
    # - Capturas:
    #   · qué ve la red (activaciones → forward hook)
    #   · qué importa para la clase (gradientes → backward hook)
    # - Ambas cosas se combinan más tarde para crear el heatmap de Grad-CAM


    # --------------------------
    # Leer y procesar imagen
    # --------------------------
    img_pil = Image.open(image_path).convert("RGB")     # Abrir imagen y asegurar RGB
    original_size = img_pil.size                        # Guardar tamaño original para redimensionar heatmap

    img_tensor = transform(img_pil).unsqueeze(0).to(device)     # Tensor [1,C,H,W] en device
    output = model(img_tensor)                          # Forward pass
    output_np = output.detach().cpu().numpy()[0]        # Convertir salida a NumPy

    heatmap_urls = []   # Lista donde guardaremos las rutas de los Grad-CAM

    # --------------------------
    # Iterar sobre clases
    # --------------------------
    for class_idx in range(len(class_names)):
        prob = output_np[class_idx]     # Probabilidad de la clase
        if prob < threshold:
            continue                    # Ignorar clases poco probables

        # --------------------------
        # Forward y backward de nuevo para la clase
        # --------------------------
        # Resetea todos los gradientes de los parámetros del modelo a cero. 
        # En PyTorch, los gradientes se acumulan por defecto, por eso hay que limpiar antes de hacer un nuevo backward.
        # Si no lo hacemos, los gradientes que guardamos en el hook podrían mezclarse con gradientes de inferencias previas, dando pesos αₖ incorrectos.
        model.zero_grad()       # Limpiar gradientes previos

        # Convierte la imagen PIL a un tensor [C,H,W] normalizado con transform.
        # unsqueeze(0) → añade dimensión de batch [1,C,H,W].
        # .to(device) → mueve la imagen a GPU o CPU según corresponda.
        img_tensor = transform(img_pil).unsqueeze(0).to(device)  # Rehacer forward

        # model(img_tensor) → ejecuta el forward pass del modelo.
        # Calcula todas las activaciones de las capas y la salida final.
        # Para Grad-CAM necesitamos los gradientes respecto a la salida de la clase de interés.
        # En algunos códigos se hace forward una sola vez, pero aquí hacemos forward nuevamente para asegurar que los gradientes se calculen correctamente después de limpiar los gradientes.
        output = model(img_tensor)

        # One-hot para la clase de interés
        # Creamos un vector one-hot para la clase que nos interesa (class_idx)
        # one_hot.shape = output.shape
        # Todos los elementos son 0, excepto la posición de la clase objetivo que es 1.
        # Queremos calcular los gradientes solo respecto a esta clase, no respecto a otras salidas del modelo.
        # Esto permite calcular el gradiente de la salida respecto a esa clase específica.
        one_hot = torch.zeros_like(output)
        one_hot[0, class_idx] = 1

        # Backward pass: calcula gradients = ∂(output de la clase objetivo)/∂(activaciones Aᵏ)
        # PyTorch calcula el gradiente de output ponderado por one_hot respecto a todas las activaciones que tienen requires_grad=True, incluyendo nuestra capa target.
        # Esto activa los hooks de backward que guardan los gradientes en gradients.
        output.backward(gradient=one_hot)   # Backward: gradientes respecto a capa target

        # En resumen: Este bloque prepara los gradientes necesarios para calcular los pesos αₖ, que luego se usarán para ponderar las activaciones y generar el heatmap de Grad-CAM.



        # --------------------------
        # Grad-CAM: calcular αₖ (pooled gradients)
        # --------------------------
        # Cada valor pooled_gradients[k] = αₖ = peso de importancia del canal k para la clase objetivo.
        # Si αₖ grande → canal importante
        # Si αₖ pequeño → canal poco relevante
        # Resultado: un vector de tamaño [C], donde C es el número de canales en la capa target.
        # Cada valor indica cuánto contribuye cada canal de la capa convolucional a la clase objetivo.
        # Se obtiene promediando los gradientes sobre H×W (y batch).
        pooled_gradients = torch.mean(gradients, dim=[0, 2, 3])     # [C] = Promedio HxW por canal


        # --------------------------
        # Ponderar activaciones por αₖ
        # --------------------------
        # Forma original: [batch_size, C, H, W]
        # squeeze(0) quita dimensión batch, quedando [C, H, W]
        # detach(), desconecta el tensor del grafo de gradientes de PyTorch. No necesitamos que estas operaciones guarden gradiente, solo vamos a calcular el heatmap.
        activations_cam = activations.squeeze(0).detach()   # [C,H,W] = activaciones de la capa target (Quitar batch y desconectar gradiente)
        
        # Toma el mapa 2D del canal i-ésimo y lo multiplica por el peso αₖ correspondiente
        # activations_cam[i, :, :]: mapa 2D del canal i-ésimo, forma [H,W]
        # pooled_gradients[i]: peso αₖ del canal i-ésimo
        for i in range(activations_cam.shape[0]):
            # Cada píxel del mapa del canal i se multiplica por αₖ.
            # Esto pondera espacialmente cada canal según su importancia para la clase objetivo.
            # Si αₖ grande → canal importante → activaciones se refuerzan
            # Si αₖ pequeño → canal poco relevante → activaciones se atenúan
            activations_cam[i, :, :] *= pooled_gradients[i]   # Multiplicar cada canal (i) por su importancia (pooled gradient)
        # Resultado: ahora cada canal tiene intensidad proporcional a su importancia. Los patrones más importantes se vuelven más brillantes, los irrelevantes se atenúan.



        # --------------------------
        # Combinar canales → heatmap 2D
        # --------------------------
        # El heatmap final se obtiene sumando todos los feature maps ponderados:
        # Lᶜ = ReLU( Σₖ αₖ Aᵏ )

        # activations_cam = [C, H, W]: Cada canal ya ha sido multiplicado por su peso αₖ (pooled_gradients[i]). Cada canal representa la activación ponderada por su importancia para la clase objetivo.
        # Ahora queremos combinar todos los canales en un solo mapa 2D [H, W] que podamos visualizar como heatmap.
        # dim=0 → sumatorio sobre todos los canales C.
        # Resultado: [H, W]
        heatmap = torch.sum(activations_cam, dim=0).cpu().numpy() # Sumatorio sobre canales

        # ReLU: solo consideramos activaciones positivas, valores negativos se ponen a 0
        heatmap = np.maximum(heatmap, 0)

        # Normalizar a [0,1]. Esto hace que podamos superponer el heatmap en la imagen de forma visual consistente.                 
        if heatmap.max() != 0:
            heatmap /= heatmap.max()

        # --------------------------
        # Superponer heatmap en imagen original
        # --------------------------
        img_cv = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR) # Convertir PIL a BGR para OpenCV 
        heatmap_resized = cv2.resize(heatmap, (img_cv.shape[1], img_cv.shape[0])) # Redimensionar heatmap al tamaño original
        heatmap_colored = cv2.applyColorMap(np.uint8(255 * heatmap_resized), cv2.COLORMAP_JET) # Colorear heatmap
        superimposed_img = cv2.addWeighted(img_cv, 0.6, heatmap_colored, 0.4, 0) # Superponer heatmap en imagen original

        # --------------------------
        # Guardar imagen
        # --------------------------
        gradcam_filename = f"gradcam_{filename.split('.')[0]}_{class_names[class_idx]}.jpg"
        gradcam_path = os.path.join(output_folder, gradcam_filename)
        cv2.imwrite(gradcam_path, superimposed_img)

        # Guardar ruta relativa
        heatmap_urls.append('/gradcam_outputs/' + gradcam_filename)

    return heatmap_urls # Devolver rutas de todos los Grad-CAM generados
