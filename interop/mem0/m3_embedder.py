#!/usr/bin/env python3
"""bge-m3 ONNX 嵌入器，严格对齐 respire-cli 的 m3 口径。

对齐依据（respire-cli/core/crates/memory-core/src/bge.rs）：
- 模型文件 `onnx/model_quantized.onnx`（M3_SPEC.file，bge.rs:56）
- CLS pooling（bge.rs:204 「BGE-M3 dense embeddings use CLS pooling」）
- 无查询前缀（M3_SPEC.prefix = ""，bge.rs:57）
- 执行截断 512 token（M3_SPEC.execution_tokens，bge.rs:53）
- L2 归一（bge.rs:206-210）
维度 1024。

不依赖 torch / sentence-transformers：本机 m3 是 Xenova/bge-m3 的 ONNX 导出，
没有 pytorch 权重，sentence-transformers 加载不了。
"""
from __future__ import annotations

import os
from typing import Iterable, List, Optional

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

DEFAULT_M3_DIR = os.path.expanduser("~/.rsrs/models/bge-m3")
MAX_TOKENS = 512          # bge.rs M3_SPEC.execution_tokens
DIMS = 1024


class M3OnnxEmbedder:
    """最小接口：embed(text) / embed_batch(texts)，返回 list[float] / list[list[float]]。"""

    def __init__(self, model_dir: str = DEFAULT_M3_DIR, threads: int = 0):
        self.model_dir = model_dir
        tok_path = os.path.join(model_dir, "tokenizer.json")
        onnx_path = os.path.join(model_dir, "onnx", "model_quantized.onnx")
        for p in (tok_path, onnx_path):
            if not os.path.isfile(p):
                raise FileNotFoundError(f"缺少 m3 文件: {p}")
        self.onnx_path = onnx_path
        self.tokenizer = Tokenizer.from_file(tok_path)
        so = ort.SessionOptions()
        if threads:
            so.intra_op_num_threads = threads
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.session = ort.InferenceSession(onnx_path, so, providers=["CPUExecutionProvider"])
        self.input_names = {i.name for i in self.session.get_inputs()}
        out = self.session.get_outputs()[0]
        self.output_name = out.name

    # ---- 内部：tokenize ----
    def _encode(self, texts: List[str]) -> dict:
        encs = [self.tokenizer.encode(t, add_special_tokens=True) for t in texts]
        for e in encs:
            if len(e.ids) > MAX_TOKENS:
                e.truncate(MAX_TOKENS, 0, "right")
        maxlen = max(len(e.ids) for e in encs)
        ids = np.zeros((len(encs), maxlen), dtype=np.int64)
        mask = np.zeros((len(encs), maxlen), dtype=np.int64)
        for i, e in enumerate(encs):
            n = len(e.ids)
            ids[i, :n] = e.ids
            mask[i, :n] = e.attention_mask
        feed = {"input_ids": ids, "attention_mask": mask}
        if "token_type_ids" in self.input_names:
            feed["token_type_ids"] = np.zeros_like(ids)
        feed = {k: v for k, v in feed.items() if k in self.input_names}
        return feed

    def embed_batch(self, texts: Iterable[str]) -> List[List[float]]:
        texts = list(texts)
        if not texts:
            return []
        feed = self._encode(texts)
        hidden = self.session.run([self.output_name], feed)[0]   # [B, T, 1024]
        cls = hidden[:, 0, :].astype(np.float32)                 # CLS pooling
        norms = np.linalg.norm(cls, axis=1, keepdims=True)
        norms[norms < 1e-8] = 1.0
        vecs = (cls / norms).astype(np.float32)                  # L2 normalize
        if vecs.shape[1] != DIMS:
            raise RuntimeError(f"维度异常 {vecs.shape[1]} ≠ {DIMS}")
        return [v.tolist() for v in vecs]

    def embed(self, text: str) -> List[float]:
        return self.embed_batch([text])[0]


_CORE = None


def core(model_dir: str = DEFAULT_M3_DIR) -> M3OnnxEmbedder:
    global _CORE
    if _CORE is None:
        _CORE = M3OnnxEmbedder(model_dir)
    return _CORE


# 模块级类：EmbedderFactory 用点路径 `m3_embedder.Mem0M3Embedding` 导入
from mem0.configs.embeddings.base import BaseEmbedderConfig  # noqa: E402
from mem0.embeddings.base import EmbeddingBase  # noqa: E402


class Mem0M3Embedding(EmbeddingBase):
    """mem0 侧适配：全部转发到 bge-m3 ONNX，绝不回落到 OpenAI。"""

    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)
        self.core = core()
        self.config.embedding_dims = DIMS

    def embed(self, text, memory_action=None):
        return self.core.embed(text)

    def embed_batch(self, texts, memory_action="add"):
        return self.core.embed_batch(texts)


def register() -> None:
    """把 m3onnx 注册进 mem0 的 embedder 工厂（唯一改动点，不碰判分器）。"""
    import sys
    from mem0.utils.factory import EmbedderFactory

    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    EmbedderFactory.provider_to_class["m3onnx"] = "m3_embedder.Mem0M3Embedding"
