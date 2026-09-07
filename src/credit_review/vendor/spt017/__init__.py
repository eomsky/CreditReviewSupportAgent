"""Read-only inference adapter for the user's frozen SPT v0.17 pipeline."""
from functools import lru_cache
from pathlib import Path
import hashlib
import json
import joblib
import sklearn

from .extractor import PDFExtractor
from .builder_base import DocumentBuilder
from .v015_rules import install_v015_builder
from .v016_rules import install_v016_builder
from .v017_rules import install_v017_builder
from .chunk_builder_v017 import ChunkBuilder, ChunkRepresentationLevel

MODEL_PATH = Path(__file__).with_name('table_region_joint_rectangular_v0.17.joblib')
MODEL_SHA256 = '76dd6405b6376a69ea6dcc3904271dd692b3752f29fd25806a8dde5b62d6f654'
PIPELINE_VERSION = 'spt017-structural-v1'


@lru_cache(maxsize=1)
def load_boundary_model():
    if sklearn.__version__ != '1.8.0':
        raise RuntimeError('SPT v0.17 requires scikit-learn==1.8.0, matching the saved model')
    if hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest() != MODEL_SHA256:
        raise RuntimeError('SPT v0.17 model checksum mismatch')
    bundle = joblib.load(MODEL_PATH)
    if bundle['feature_names'] != DocumentBuilder.FEATURE_NAMES:
        raise ValueError('SPT v0.17 feature schema mismatch')
    # Small per-table batches: avoid spawning CPU thread pools for each prediction.
    bundle['joint_model'].n_jobs = 1
    return bundle


class InferenceBase(DocumentBuilder):
    def _prepare_boundary_model(self, tables=None):
        bundle = load_boundary_model()
        return bundle, {**bundle['training_report'], 'mode': 'LOAD', 'model_sha256': MODEL_SHA256}


StructuralBuilder = install_v017_builder(install_v016_builder(install_v015_builder(InferenceBase)))


def extract_document(path):
    raw = PDFExtractor().extract(str(path))
    master = StructuralBuilder().build(raw)
    chunks = ChunkBuilder(representation_level=ChunkRepresentationLevel.HIERARCHICAL).build(master)
    return master, chunks
