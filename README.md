# SMART SPRAY — AI/ML & GenAI Core

**Team Role**: Person 1 (AI/ML + GenAI Module Specialist)  
**Scope**: Open-world crop identification, disease/pest/nutrient diagnosis, climate risk AI, agricultural RAG knowledge base, verified treatment database, and farmer-friendly GenAI explanations.  
**Explicitly Excluded**: Frontend UI, backend web services, ESP32 firmware, pump control logic, and final decision engine.

---

## 🏛️ Architecture & Project Flow

```mermaid
flowchart TD
    Cam[Camera Image] --> ImgLoader[Image Loader & Preprocessor]
    ImgLoader --> CropMod[1. Plant/Crop Identification\n(Gemini 3.8 Flash Multimodal)]
    ImgLoader --> DisMod[2. Disease Detection\n(CV / YOLO + Classifier)]
    ImgLoader --> PestMod[3. Pest Detection\n(YOLO BBoxes & Counts)]
    ImgLoader --> NutrMod[4. Nutrient Deficiency\n(Visual Indicators)]
    ImgLoader --> SevMod[5. Severity Assessment\n(Affected Area %)]
    
    Sensors[IoT Sensors & Weather] --> ClimMod[6. Climate-Risk AI\n(Drought, Heat, Flood, Waterlog)]
    
    CropMod & DisMod & PestMod & NutrMod & SevMod & ClimMod --> Pipe[10. Unified analyze_field Pipeline]
    
    Pipe --> DE[Person 2 Decision Engine\n(Spray OR Warning)]
    
    Pipe --> RAG[7. Agricultural RAG & 8. Verified Treatment DB]
    RAG --> GenAI[9. GenAI Explanation Engine\n(Evidence & Advice)]
```

---

## 📁 AI Module Directory Structure

```
smart_spray_ai/
├── ai/
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py          # Confidence thresholds, API keys, model configurations
│   ├── schemas/
│   │   ├── crop.py              # CropIdentificationResult, confidence tiers
│   │   ├── disease.py           # DiseaseDetectionResult, BoundingBox
│   │   ├── pest.py              # PestDetectionResult, DetectedPest
│   │   ├── nutrient.py          # NutrientDeficiencyResult (N, P, K, Fe, Mg, Zn)
│   │   ├── severity.py          # SeverityAssessmentResult (healthy -> critical)
│   │   ├── climate.py           # Soil, Air, Weather forecast, and ClimateRiskResult
│   │   ├── treatment.py         # VerifiedTreatmentRecord (strict fields, no hallucinations)
│   │   ├── pipeline.py          # FieldAnalysisOutput contract for Person 2's Decision Engine
│   │   └── explanation.py       # GenAI explanation schemas
│   ├── models/
│   │   ├── base.py              # BaseVisionModel abstract interface
│   │   ├── crop/                # Phase 1: Open-world plant/crop identification
│   │   │   ├── base.py          # BaseCropIdentifier interface
│   │   │   ├── gemini_vision.py # Gemini 3.8 Flash multimodal vision model
│   │   │   ├── mock_crop.py     # Deterministic offline mock for CI/testing
│   │   │   └── __init__.py      # get_crop_identifier() factory
│   │   ├── disease/             # Phase 2: Disease detection
│   │   ├── pest/                # Phase 2: Pest detection & counting
│   │   ├── nutrient/            # Phase 2: Visual nutrient deficiency
│   │   └── severity/            # Phase 2: Damage & severity estimation
│   ├── risk/                    # Phase 3: Climate-risk rules/RF/XGBoost
│   ├── rag/                     # Phase 4: Agricultural knowledge base & vector store
│   ├── treatment/               # Phase 4: Verified treatment catalog
│   ├── genai/                   # Phase 5: Post-diagnosis farmer-friendly explanation
│   └── inference/
│       ├── __init__.py
│       └── image_loader.py      # Universal image loader (PIL, path, bytes, Base64)
├── data/
│   ├── sample_images/           # Test & synthetic crop images
│   ├── mock_sensors/            # Telemetry JSON fixtures
│   └── mock_weather/            # Weather forecast JSON fixtures
├── tests/
│   ├── conftest.py              # Shared fixtures
│   ├── test_schemas.py          # Contract and validation tests
│   ├── test_image_loader.py     # Universal image reader tests
│   ├── test_confidence_rules.py # Confidence governance & confirmation flags
│   └── test_crop_identification.py # Mock & live vision tests
├── requirements.txt
└── README.md
```

---

## 🚀 Quickstart & Phase 1 Usage

### 1. Installation
Ensure Python 3.11+ is installed, then install the package dependencies:
```bash
pip install -r requirements.txt
```

### 2. Environment Configuration (Optional)
To enable live open-world crop identification via Google Gemini:
```bash
# Windows PowerShell
$env:GEMINI_API_KEY="your-gemini-api-key"

# Or create a .env file in the smart_spray_ai/ root:
# GEMINI_API_KEY=your-gemini-api-key
```
If no key is configured, the system automatically runs in offline `Mock` mode.

### 3. Programmatic Usage (Crop Identification)
```python
from ai.models.crop import get_crop_identifier

# Automatically select Gemini (if API key present) or Mock fallback
identifier = get_crop_identifier(mode="auto")

# Accepts file paths, PIL Images, byte buffers, or Base64 strings
result = identifier.identify("ai/data/sample_images/sample_tomato.jpg")

print(f"Detected Crop: {result.crop_name}")
print(f"Scientific Name: {result.scientific_name}")
print(f"Confidence: {result.confidence:.2f} ({result.confidence_level})")
print(f"Requires Confirmation: {result.requires_confirmation}")
print(f"Visible Parts: {result.detected_parts}")
print(f"Reasoning: {result.reasoning}")
```

### 4. Running Test Suite
Execute pytest across all unit and contract tests:
```bash
python -m pytest tests/ -v
```

---

## 🎯 Confidence-Aware Governance
Per project requirements:
- **High Confidence (`>= 0.85`)**: Direct confirmation not required (`requires_confirmation: false`).
- **Moderate Confidence (`0.60 – 0.85`)**: Diagnosis recorded; flagged for tracking.
- **Low Confidence (`< 0.60`)**: Sets `requires_confirmation: true`. Will **never** automatically trigger pesticide or chemical treatments downstream.
- **Non-Plant / Ambiguous Input**: Sets `requires_confirmation: true` and categorizes the input accordingly.
