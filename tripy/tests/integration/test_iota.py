#
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
#

import cupy as cp
import numpy as np
import pytest

import tripy as tp

from tripy.common.datatype import DATA_TYPES
from tests import helper


class TestIota:
    DTYPE_PARAMS = [
        (("float32", tp.common.datatype.float32)),
        (("float16", tp.common.datatype.float16)),
        (("int32", tp.common.datatype.int32)),
    ]

    def _compute_ref_iota(self, dtype, shape, dim):
        if dim is None:
            dim = 0
        elif dim < 0:
            dim += len(shape)
        expected = np.arange(0, shape[dim], dtype=dtype)
        if dim < len(shape) - 1:
            expand_dims = [1 + i for i in range(len(shape) - 1 - dim)]
            expected = np.expand_dims(expected, expand_dims)
        expected = np.broadcast_to(expected, shape)
        return expected

    @pytest.mark.parametrize("dtype", DTYPE_PARAMS)
    @pytest.mark.parametrize(
        "shape, dim",
        [
            ((2, 3), 1),
            ((2, 3), None),
            ((2, 3), -1),
            ((2, 3, 4), 2),
        ],
    )
    def test_iota(self, dtype, shape, dim):
        if dim:
            output = tp.iota(shape, dim, dtype[1])
        else:
            output = tp.iota(shape, dtype=dtype[1])

        assert np.array_equal(cp.from_dlpack(output).get(), self._compute_ref_iota(dtype[0], shape, dim))

    @pytest.mark.parametrize("dtype", DTYPE_PARAMS)
    @pytest.mark.parametrize(
        "shape, dim",
        [
            ((2, 3), 1),
            ((2, 3), None),
            ((2, 3), -1),
            ((2, 3, 4), 2),
        ],
    )
    def test_iota_like(self, dtype, shape, dim):
        if dim:
            output = tp.iota_like(tp.ones(shape), dim, dtype[1])
        else:
            output = tp.iota_like(tp.ones(shape), dtype=dtype[1])

        assert np.array_equal(cp.from_dlpack(output).get(), self._compute_ref_iota(dtype[0], shape, dim))

    @pytest.mark.parametrize("dtype", DATA_TYPES.values())
    def test_negative_no_casting(self, dtype):
        from tripy.frontend.trace.ops.iota import Iota

        if dtype in [tp.float32, tp.int32, tp.int64]:
            pytest.skip("tp.iota() supports float32, int32, and int64 without cast")

        # TODO: update the 'match' error msg when MLIR-TRT fixes dtype constraint
        a = tp.ones((2, 2))
        out = Iota.build([a.shape], dim=0, output_rank=2, dtype=dtype)

        exception_str = "error: 'tensorrt.linspace' op result #0 must be 0D/1D/2D/3D/4D/5D/6D/7D/8D tensor of 32-bit float or 32-bit signless integer values"
        if dtype == tp.bool:
            exception_str = "InternalError: failed to run compilation"
        with helper.raises(
            tp.TripyException,
            match=exception_str,
        ):
            print(out)

    def test_iota_from_shape_tensor(self):
        a = tp.ones((2, 2))
        output = tp.iota(a.shape)
        assert np.array_equal(cp.from_dlpack(output).get(), self._compute_ref_iota("float32", (2, 2), 0))

    def test_iota_from_mixed_seqence(self):
        a = tp.ones((2, 2))
        output = tp.iota((3, a.shape[0]))
        assert np.array_equal(cp.from_dlpack(output).get(), self._compute_ref_iota("float32", (3, 2), 0))