"""
Configurable Crop-Aware Disease Registry.
Decouples crop-to-disease mappings from inference algorithms to prevent cross-crop diagnostic errors.
"""

from typing import Any, Dict, List, Optional, Set
from pathlib import Path
import json


class CropDiseaseRegistry:
    """
    Central registry for crop-specific disease mappings, symptoms, and pathogens.
    Configurable via Python dictionaries or external JSON files.
    """

    DEFAULT_CATALOG: Dict[str, Dict[str, Dict[str, str]]] = {
        "tomato": {
            "early_blight": {
                "display_name": "Early Blight",
                "pathogen": "Alternaria solani",
                "symptoms": "Concentric rings, target-like brown lesions on older leaves, yellow halo",
            },
            "late_blight": {
                "display_name": "Late Blight",
                "pathogen": "Phytophthora infestans",
                "symptoms": "Water-soaked dark lesions, white fungal growth under humid conditions",
            },
            "bacterial_spot": {
                "display_name": "Bacterial Spot",
                "pathogen": "Xanthomonas vesicatoria",
                "symptoms": "Small, water-soaked, dark brown circular spots with yellow borders",
            },
            "septoria_leaf_spot": {
                "display_name": "Septoria Leaf Spot",
                "pathogen": "Septoria lycopersici",
                "symptoms": "Numerous small circular spots with grey centers and dark margins",
            },
            "yellow_leaf_curl_virus": {
                "display_name": "Tomato Yellow Leaf Curl Virus",
                "pathogen": "TYLCV (Begomovirus)",
                "symptoms": "Upward curling leaves, chlorosis, stunting, reduced fruit yield",
            },
            "healthy": {
                "display_name": "Healthy Tomato",
                "pathogen": "None",
                "symptoms": "Vigorous green foliage with no pathological lesions",
            },
        },
        "potato": {
            "early_blight": {
                "display_name": "Early Blight",
                "pathogen": "Alternaria solani",
                "symptoms": "Concentric circular lesions, foliar necrosis",
            },
            "late_blight": {
                "display_name": "Late Blight",
                "pathogen": "Phytophthora infestans",
                "symptoms": "Purplish-brown lesions spreading rapidly across foliage",
            },
            "healthy": {
                "display_name": "Healthy Potato",
                "pathogen": "None",
                "symptoms": "Intact green leaves without necrotic spots",
            },
        },
        "maize": {
            "common_rust": {
                "display_name": "Common Rust",
                "pathogen": "Puccinia sorghi",
                "symptoms": "Cinnamon-brown pustules scattered across leaf surfaces",
            },
            "northern_leaf_blight": {
                "display_name": "Northern Corn Leaf Blight",
                "pathogen": "Exserohilum turcicum",
                "symptoms": "Long, elliptical grayish-green cigar-shaped lesions",
            },
            "healthy": {
                "display_name": "Healthy Maize",
                "pathogen": "None",
                "symptoms": "Uniform green blades with no fungal pustules",
            },
        },
        "grape": {
            "black_rot": {
                "display_name": "Black Rot",
                "pathogen": "Guignardia bidwellii",
                "symptoms": "Reddish-brown leaf spots with black fruiting bodies (pycnidia)",
            },
            "powdery_mildew": {
                "display_name": "Powdery Mildew",
                "pathogen": "Erysiphe necator",
                "symptoms": "Dusty white-to-gray fungal coating on leaf surfaces",
            },
            "healthy": {
                "display_name": "Healthy Grape",
                "pathogen": "None",
                "symptoms": "Healthy vine leaves without fungal powder or necrosis",
            },
        },
        "apple": {
            "apple_scab": {
                "display_name": "Apple Scab",
                "pathogen": "Venturia inaequalis",
                "symptoms": "Olive-green to black velvety spots on leaves",
            },
            "cedar_apple_rust": {
                "display_name": "Cedar Apple Rust",
                "pathogen": "Gymnosporangium juniperi-virginianae",
                "symptoms": "Bright orange-yellow spots on upper leaf surfaces",
            },
            "healthy": {
                "display_name": "Healthy Apple",
                "pathogen": "None",
                "symptoms": "Unblemished green leaves",
            },
        },
    }

    def __init__(self, initial_catalog: Optional[Dict[str, Any]] = None):
        self._catalog: Dict[str, Dict[str, Dict[str, str]]] = (
            initial_catalog.copy() if initial_catalog else self.DEFAULT_CATALOG.copy()
        )

    def normalize_crop_name(self, crop: str) -> str:
        """Normalize crop identifier."""
        norm = crop.strip().lower()
        if norm == "corn":
            return "maize"
        return norm

    def is_crop_supported(self, crop: str) -> bool:
        """Check if a crop has an active disease diagnostic profile."""
        norm = self.normalize_crop_name(crop)
        return norm in self._catalog

    def get_supported_crops(self) -> List[str]:
        """Return list of all registered crops."""
        return sorted(list(self._catalog.keys()))

    def get_supported_diseases(self, crop: str) -> List[str]:
        """Return list of valid disease identifiers for given crop."""
        norm = self.normalize_crop_name(crop)
        if norm not in self._catalog:
            return []
        return list(self._catalog[norm].keys())

    def is_disease_valid_for_crop(self, crop: str, disease: str) -> bool:
        """Verify whether a disease is biologically recognized for the specified crop."""
        norm_crop = self.normalize_crop_name(crop)
        norm_disease = disease.strip().lower()
        if norm_crop not in self._catalog:
            return False
        return norm_disease in self._catalog[norm_crop]

    def get_disease_metadata(self, crop: str, disease: str) -> Optional[Dict[str, str]]:
        """Retrieve pathogen, symptoms, and display name for a crop's disease."""
        norm_crop = self.normalize_crop_name(crop)
        norm_disease = disease.strip().lower()
        if self.is_disease_valid_for_crop(norm_crop, norm_disease):
            return self._catalog[norm_crop][norm_disease]
        return None

    def get_display_name(self, crop: str, disease: str) -> str:
        """Get human-readable display name."""
        meta = self.get_disease_metadata(crop, disease)
        if meta and "display_name" in meta:
            return meta["display_name"]
        return disease.replace("_", " ").title()

    def register_crop_disease(
        self,
        crop: str,
        disease: str,
        display_name: str,
        pathogen: str = "Unknown",
        symptoms: str = "",
    ) -> None:
        """Dynamically add or update a crop disease in the registry."""
        norm_crop = self.normalize_crop_name(crop)
        norm_disease = disease.strip().lower()
        if norm_crop not in self._catalog:
            self._catalog[norm_crop] = {}
        self._catalog[norm_crop][norm_disease] = {
            "display_name": display_name,
            "pathogen": pathogen,
            "symptoms": symptoms,
        }

    def load_from_json(self, json_path: Path) -> None:
        """Load external disease registry configuration from JSON file."""
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self._catalog.update(data)


# Global singleton instance
_GLOBAL_REGISTRY = CropDiseaseRegistry()


def get_disease_registry() -> CropDiseaseRegistry:
    """Return central crop disease registry."""
    return _GLOBAL_REGISTRY
