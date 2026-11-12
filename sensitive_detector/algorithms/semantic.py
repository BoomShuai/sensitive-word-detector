"""Explicit, local-only embeddings; model errors never silently change the backend."""
from pathlib import Path


class SemanticBackend:
    def __init__(self, model_name, sim_threshold=0.55, high_sim_threshold=0.70, device="cpu"):
        self.path = Path(model_name).expanduser().resolve()
        if not self.path.is_dir():
            raise ValueError("语义模式需要已存在的本地模型目录")
        self.sim_threshold = sim_threshold
        self.high_sim_threshold = high_sim_threshold
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(str(self.path), device=device, local_files_only=True, trust_remote_code=False)
        except Exception as error:
            raise RuntimeError("本地语义模型加载失败；请核对 semantic 依赖和模型完整性") from error

    @property
    def available(self):
        return True

    def encode_batch(self, texts):
        try:
            import numpy as np
            texts = list(texts)
            vectors = np.asarray(self._model.encode(texts, normalize_embeddings=True, convert_to_numpy=True,
                                                   batch_size=32, show_progress_bar=False))
            if vectors.ndim != 2 or vectors.shape[0] != len(texts) or vectors.shape[1] == 0 or not np.isfinite(vectors).all():
                raise ValueError("Invalid embedding matrix")
            return vectors
        except Exception as error:
            raise RuntimeError("本地语义模型推理失败，未自动切换到规则模式") from error

    def precompute_templates(self, templates):
        return self.encode_batch(templates)
