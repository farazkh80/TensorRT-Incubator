# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.

# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.

import math
from typing import Optional

from sam2.modeling.sam.transformer import RoPEAttention
from sam2.modeling.sam2_utils import get_activation_fn, get_clones

# from sam2.modeling.sam.transformer import RoPEAttention
# from sam2.modeling.sam2_utils import get_activation_fn, get_clones

import tripy as tp


class MemoryAttentionLayer(tp.Module):
    def __init__(
        self,
        activation: str,
        cross_attention: tp.Module,
        d_model: int,
        dim_feedforward: int,
        dropout: float,
        pos_enc_at_attn: bool,
        pos_enc_at_cross_attn_keys: bool,
        pos_enc_at_cross_attn_queries: bool,
        self_attention: tp.Module,
    ):
        super().__init__()
        self.d_model = d_model
        self.dim_feedforward = dim_feedforward
        self.self_attn = self_attention
        self.cross_attn_image = cross_attention

        # Implementation of Feedforward model
        self.linear1 = tp.Linear(d_model, dim_feedforward)
        self.linear2 = tp.Linear(dim_feedforward, d_model)

        self.norm1 = tp.LayerNorm(d_model)
        self.norm2 = tp.LayerNorm(d_model)
        self.norm3 = tp.LayerNorm(d_model)

        self.activation_str = activation
        self.activation = get_activation_fn(activation)

        # Where to add pos enc
        self.pos_enc_at_attn = pos_enc_at_attn
        self.pos_enc_at_cross_attn_queries = pos_enc_at_cross_attn_queries
        self.pos_enc_at_cross_attn_keys = pos_enc_at_cross_attn_keys

    def _forward_sa(self, tgt, query_pos):
        # Self-Attention
        tgt2 = self.norm1(tgt)
        q = k = tgt2 + query_pos if self.pos_enc_at_attn else tgt2
        tgt2 = self.self_attn(q, k, v=tgt2)
        tgt = tgt
        return tgt

    def _forward_ca(self, tgt, memory, query_pos, pos, num_k_exclude_rope=0):
        kwds = {}
        if num_k_exclude_rope > 0:
            assert isinstance(self.cross_attn_image, RoPEAttention)
            kwds = {"num_k_exclude_rope": num_k_exclude_rope}

        # Cross-Attention
        tgt2 = self.norm2(tgt)
        tgt2 = self.cross_attn_image(
            q=tgt2 + query_pos if self.pos_enc_at_cross_attn_queries else tgt2,
            k=memory + pos if self.pos_enc_at_cross_attn_keys else memory,
            v=memory,
            **kwds,
        )
        tgt = tgt
        return tgt

    def __call__(
        self,
        tgt,
        memory,
        pos: Optional[tp.Tensor] = None,
        query_pos: Optional[tp.Tensor] = None,
        num_k_exclude_rope: int = 0,
    ) -> tp.Tensor:

        # Self-Attn, Cross-Attn
        tgt = self._forward_sa(tgt, query_pos)
        tgt = self._forward_ca(tgt, memory, query_pos, pos, num_k_exclude_rope)
        # MLP
        tgt2 = self.norm3(tgt)
        tgt2 = self.linear2(self.activation(self.linear1(tgt2)))
        tgt = tgt + tgt2
        return tgt


class MemoryAttention(tp.Module):
    def __init__(
        self,
        d_model: int,
        pos_enc_at_input: bool,
        layer: tp.Module,
        num_layers: int,
        batch_first: bool = True,  # Do layers expect batch first input?
    ):
        super().__init__()
        self.d_model = d_model
        self.layers = get_clones(layer, num_layers)
        self.num_layers = num_layers
        self.norm = tp.LayerNorm(d_model)
        self.pos_enc_at_input = pos_enc_at_input
        self.batch_first = batch_first

    def __call__(
        self,
        curr: tp.Tensor,  # self-attention inputs
        memory: tp.Tensor,  # cross-attention inputs
        curr_pos: Optional[tp.Tensor] = None,  # pos_enc for self-attention inputs
        memory_pos: Optional[tp.Tensor] = None,  # pos_enc for cross-attention inputs
        num_obj_ptr_tokens: int = 0,  # number of object pointer *tokens*
    ):
        if isinstance(curr, list):
            assert isinstance(curr_pos, list)
            assert len(curr) == len(curr_pos) == 1
            curr, curr_pos = (
                curr[0],
                curr_pos[0],
            )

        assert curr.shape[1] == memory.shape[1], "Batch size must be the same for curr and memory"

        output = curr
        if self.pos_enc_at_input and curr_pos is not None:
            output = output + 0.1 * curr_pos

        if self.batch_first:
            # Convert to batch first
            output = tp.transpose(output, 0, 1)
            memory = tp.transpose(memory, 0, 1)
            if curr_pos is not None:
                curr_pos = tp.transpose(curr_pos, 0, 1)
            if memory_pos is not None:
                memory_pos = tp.transpose(memory_pos, 0, 1)

        for layer in self.layers:
            kwds = {}
            if isinstance(layer.cross_attn_image, RoPEAttention):
                kwds = {"num_k_exclude_rope": num_obj_ptr_tokens}

            output = layer(
                tgt=output,
                memory=memory,
                pos=memory_pos,
                query_pos=curr_pos,
                **kwds,
            )
        normed_output = self.norm(output)

        if self.batch_first:
            # Convert back to seq first
            normed_output = tp.transpose(normed_output, 0, 1)
            curr_pos = tp.transpose(curr_pos, 0, 1)

        return normed_output


mal = MemoryAttentionLayer(
    activation="relu",
    cross_attention=RoPEAttention(embedding_dim=256, num_heads=1),
    d_model=256,
    dim_feedforward=2048,
    dropout=0.0,
    pos_enc_at_attn=False,
    pos_enc_at_cross_attn_keys=True,
    pos_enc_at_cross_attn_queries=False,
    self_attention=RoPEAttention(embedding_dim=256, num_heads=1),
)

ma = MemoryAttention(256, True, mal, 2)
# print(ma)
print(ma(curr=tp.ones((1, 256, 256, 256)), memory=tp.ones((1, 256, 256, 256))))
