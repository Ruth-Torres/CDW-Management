# CDW-Management

Efficient management of Construction and Demolition Waste (CDW) is a global challenge due to its large volume and heterogeneity. Traditional methods, based on manual inspections and physical weighing, are slow, labor-intensive, and prone to errors. This project proposes an automated system using computer vision to identify and classify waste materials in real time via surveillance cameras.

## Dataset
This GitHub repository includes the code and ONLY the final model to launch the application. All images, labels and models (all architectures and versions) Will be published at a Mendeley Data repository (link not available yet).

## Features

- **Automated Classification**: Uses deep learning to classify different types of construction and demolition waste.
- **Real-time Analysis**: Integrates with cameras to perform predictions on live video streams.
- **Web-based Interface**: Provides an intuitive and accessible interface for users to upload images, view predictions, and analyze statistics.
- **Grad-CAM Visualization**: Highlights regions in images that the model focuses on for its predictions.
- **Export Results**: Save prediction data in CSV format for further analysis.
- **Session Management**: Clear session data to restart analysis without interference from previous results.

## Model Architecture

Three deep learning architectures were evaluated:

- **Faster R-CNN**
- **YOLOv5**
- **ResNet50** (final model chosen)

The final model, **ResNet50**, was selected for its performance and suitability for classifying complex images of mixed materials.

## Installation

1. Clone this repository:

```bash
git clone https://github.com/Ruth-Torres/CDW-Management.git
cd CDW-Management
````

2. Installation

- Ensure you have **Python** installed. This project was made with **Python 3.12.6**. In case of incompatibility of versions, install **Python 3.12.6** from [Python official site](https://www.python.org/downloads/release/python-3126/).
2. Install **PyTorch** with CUDA support if a GPU is available. For example, you can follow instructions from [PyTorch official site](https://pytorch.org/get-started/locally/):

```bash
# Example for Linux with CUDA 12.6
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126
````

- Install **Flask**:

```bash
pip install flask
```

## Usage

1. Start the Flask application (the main app file is: CDW-Management/AppWeb/app.py):

```bash
python app.py
```

2. Open a browser and navigate to:

```
http://127.0.0.1:5000/
```

3. Use the web interface to upload images or activate the live camera feed to perform classification.

## Results

* The system provides per-image predictions with confidence scores.
* Grad-CAM maps are available for high-probability predictions (>50%) to help interpret model decisions.
* Session statistics and graphical summaries of predictions are available via the interface.
* Results can be exported in CSV format for analysis.

## Future Improvements

* Expand the dataset with additional material classes (metal, plastic, wood, glass) and diverse environmental conditions.
* Explore more advanced architectures (Vision Transformers, Swin Transformer) and ensemble methods.
* Deploy in real industrial environments and integrate with plant management systems.
* Implement automated hyperparameter tuning and self-supervised learning techniques.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
