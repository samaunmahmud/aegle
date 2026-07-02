# Chest X-Ray Classifier — Java + DL4J + Spring Boot

A CNN-based medical image classifier that detects **pneumonia** in chest X-rays.
Built entirely in Java using **Deeplearning4j** for the ML pipeline and **Spring Boot** for the web server.

## Tech Stack

| Layer | Technology |
|---|---|
| ML framework | Deeplearning4j (DL4J) 1.0.0-M2.1 |
| ND array backend | ND4J Native (CPU) |
| Image loading | DataVec / NativeImageLoader |
| Web server | Spring Boot 3.2 |
| Build tool | Maven |
| Java version | 17+ |

## CNN Architecture

```
Input: 1 × 64 × 64 (grayscale)
  │
  ├── Conv2D(32, 3×3, ReLU) → MaxPool(2×2)
  ├── Conv2D(64, 3×3, ReLU) → MaxPool(2×2)
  ├── Conv2D(128, 3×3, ReLU) → MaxPool(2×2)
  │
  ├── Flatten → Dense(256, ReLU) → Dropout(0.5)
  └── Dense(2, Softmax)  →  [NORMAL | PNEUMONIA]
```

## Dataset

Download the **Chest X-Ray Images (Pneumonia)** dataset from Kaggle:
https://www.kaggle.com/datasets/paultimothymooney/chest-xray-pneumonia

After downloading, unzip it so your project looks like this:

```
medical-image-classifier/
  dataset/
    chest_xray/
      train/
        NORMAL/         ← ~1341 images
        PNEUMONIA/      ← ~3875 images
      test/
        NORMAL/         ← ~234 images
        PNEUMONIA/      ← ~390 images
      val/
        NORMAL/
        PNEUMONIA/
  pom.xml
  src/
  ...
```

## Quickstart

### 1. Build the project

```bash
mvn clean package -DskipTests
```

### 2. Run the app

```bash
mvn spring-boot:run
```

Or run the packaged jar:

```bash
java -jar target/medical-image-classifier-1.0.0.jar
```

The server starts on **http://localhost:8080**

### 3. Train the model

Before making predictions, you need to train the CNN once.
Either click "Train" in the UI, or call the REST API:

```bash
curl -X POST http://localhost:8080/api/train
```

Training takes ~5–20 minutes on CPU (10 epochs, 64×64 images).
The trained model is saved to `saved-model/xray-cnn.zip` and reloaded automatically.

### 4. Make predictions

Open **http://localhost:8080** in your browser, drag in a chest X-ray image, and click **Analyse X-Ray**.

Or use curl:

```bash
curl -X POST http://localhost:2005/api/predict \
  -F "image=@/path/to/xray.jpg"
```

Response:
```json
{
  "label": "PNEUMONIA",
  "confidence": 0.9312,
  "normalProbability": 0.0688,
  "pneumoniaProbability": 0.9312,
  "modelLoaded": true
}
```

## REST API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/status` | Check if model is loaded |
| `POST` | `/api/train` | Train the CNN (blocks until done) |
| `POST` | `/api/predict` | Classify an uploaded image |

## Configuration (`application.properties`)

```properties
# Change dataset or model paths if needed
app.dataset.path=dataset/chest_xray
app.model.path=saved-model/xray-cnn.zip

# Image size fed to the CNN
app.image.height=64
app.image.width=64
app.image.channels=1    # 1 = grayscale

# Training
app.training.epochs=10
app.training.batch-size=32
app.training.learning-rate=0.001
```

## Project Structure

```
src/main/java/com/medclassifier/
  MedicalClassifierApplication.java   ← Spring Boot entry point
  controller/
    ClassifierController.java         ← REST endpoints
  service/
    ModelTrainer.java                 ← CNN definition & training loop
    PredictionService.java            ← Model loading & inference
  model/
    PredictionResult.java             ← API response DTO

src/main/resources/
  application.properties
  static/
    index.html                        ← Web UI (drag & drop)
```

## Expected Performance

On the Kaggle chest X-ray dataset with default settings (10 epochs, 64×64):

| Metric | Approximate value |
|---|---|
| Test accuracy | ~75–85% |
| Training time (CPU) | 10–20 min |

Accuracy can be improved by increasing image size to 128×128, adding data augmentation, or using more epochs.

## Disclaimer

This project is for **educational and portfolio purposes only**.
It is **not** a certified medical device and must not be used for clinical diagnosis.
