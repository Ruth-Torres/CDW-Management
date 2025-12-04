import torch
import numpy as np
import cv2
from PIL import Image
from torchvision import transforms
import os

# Transformaciones
transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406],
                         std=[0.229, 0.224, 0.225])
])

def set_relu_inplace(module):
    for child in module.children():
        if isinstance(child, torch.nn.ReLU):
            child.inplace = False
        else:
            set_relu_inplace(child)

def generate_gradcam_image(image_path, filename, model, device, class_names, output_folder, threshold=0.5):
    """Genera y guarda heatmaps Grad-CAM para clases relevantes."""
    os.makedirs(output_folder, exist_ok=True)
    set_relu_inplace(model)

    gradients = None
    activations = None

    def save_gradient(module, grad_input, grad_output):
        nonlocal gradients
        gradients = grad_output[0]

    def forward_hook(module, input, output):
        nonlocal activations
        activations = output

    target_layer = model.layer4[-1].conv3
    target_layer.register_forward_hook(forward_hook)
    target_layer.register_full_backward_hook(save_gradient)

    img_pil = Image.open(image_path).convert("RGB")
    original_size = img_pil.size

    img_tensor = transform(img_pil).unsqueeze(0).to(device)
    output = model(img_tensor)
    output_np = output.detach().cpu().numpy()[0]

    heatmap_urls = []

    for class_idx in range(len(class_names)):
        prob = output_np[class_idx]
        if prob < threshold:
            continue

        # Re-forward
        model.zero_grad()
        img_tensor = transform(img_pil).unsqueeze(0).to(device)
        output = model(img_tensor)

        one_hot = torch.zeros_like(output)
        one_hot[0, class_idx] = 1
        output.backward(gradient=one_hot)

        pooled_gradients = torch.mean(gradients, dim=[0, 2, 3])
        activations_cam = activations.squeeze(0).detach()
        for i in range(activations_cam.shape[0]):
            activations_cam[i, :, :] *= pooled_gradients[i]

        heatmap = torch.mean(activations_cam, dim=0).cpu().numpy()
        heatmap = np.maximum(heatmap, 0)
        if heatmap.max() != 0:
            heatmap /= heatmap.max()

        img_cv = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
        heatmap_resized = cv2.resize(heatmap, (img_cv.shape[1], img_cv.shape[0]))
        heatmap_colored = cv2.applyColorMap(np.uint8(255 * heatmap_resized), cv2.COLORMAP_JET)
        superimposed_img = cv2.addWeighted(img_cv, 0.6, heatmap_colored, 0.4, 0)

        gradcam_filename = f"gradcam_{filename.split('.')[0]}_{class_names[class_idx]}.jpg"
        gradcam_path = os.path.join(output_folder, gradcam_filename)
        cv2.imwrite(gradcam_path, superimposed_img)

        heatmap_urls.append('/gradcam_outputs/' + gradcam_filename)

    return heatmap_urls
