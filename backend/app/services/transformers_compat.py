"""Compatibility helpers for Transformers utilities that RF-DETR still expects."""

from __future__ import annotations

from typing import Iterable, Optional, Set, Tuple

import importlib

import torch


def ensure_transformers_prune_utils() -> None:
    """Ensure compatibility shims for immigrants from Transformers <5.0."""

    _ensure_find_pruneable_heads()
    _ensure_backbone_utils()


def _ensure_find_pruneable_heads() -> None:
    pytorch_utils = importlib.import_module("transformers.pytorch_utils")
    if hasattr(pytorch_utils, "find_pruneable_heads_and_indices"):
        return

    def find_pruneable_heads_and_indices(
        heads: Iterable[int],
        n_heads: int,
        head_size: int,
        already_pruned_heads: Optional[Set[int]] = None,
    ) -> Tuple[Set[int], torch.Tensor]:
        already_pruned_heads = set(already_pruned_heads or ())
        mask = torch.ones(n_heads, head_size)
        heads_to_prune = set(heads) - already_pruned_heads
        for head in heads_to_prune:
            head = head - sum(1 if h < head else 0 for h in already_pruned_heads)
            mask[head] = 0
        mask = mask.view(-1).contiguous().eq(1)
        index: torch.LongTensor = torch.arange(mask.size(0))[mask].long()
        return heads_to_prune, index

    pytorch_utils.find_pruneable_heads_and_indices = find_pruneable_heads_and_indices


def _ensure_backbone_utils() -> None:
    backbone_utils = importlib.import_module("transformers.utils.backbone_utils")
    if hasattr(backbone_utils, "get_aligned_output_features_output_indices"):
        return

    from transformers.backbone_utils import BackboneConfigMixin as _BackboneConfigMixin

    class _BackboneHelper(_BackboneConfigMixin):
        def __init__(self, stage_names: Iterable[str]):
            self.stage_names = list(stage_names)
            self._out_features = None
            self._out_indices = None

    def get_aligned_output_features_output_indices(
        *,
        out_features: Iterable[str] | None,
        out_indices: Iterable[int] | None,
        stage_names: Iterable[str],
    ) -> Tuple[list[str] | None, list[int] | None]:
        helper = _BackboneHelper(stage_names)
        helper.set_output_features_output_indices(
            out_features=list(out_features) if out_features is not None else None,
            out_indices=list(out_indices) if out_indices is not None else None,
        )
        return helper._out_features, helper._out_indices

    backbone_utils.get_aligned_output_features_output_indices = (
        get_aligned_output_features_output_indices
    )
