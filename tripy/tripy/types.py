#
# SPDX-FileCopyrightText: Copyright (c) 2024-2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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

"""
Special type annotations used in Tripy.
"""

import numbers
import sys
from typing import Union, Sequence

from tripy import export

export.public_api()(sys.modules[__name__])

NestedNumberSequence = export.public_api(
    document_under="types.rst",
    autodoc_options=[":no-index:"],
    module=sys.modules[__name__],
    symbol="NestedNumberSequence",
)(Union[numbers.Number, Sequence["tripy.types.NestedNumberSequence"]])

NestedNumberSequence.__doc__ = """
Denotes the recursive type annotation for sequences of Python numbers, possibly nested to an arbitrary depth.
Tripy often automatically converts these sequences to `tp.Tensor`.
"""

TensorLike = export.public_api(
    document_under="types.rst",
    autodoc_options=[":no-index:"],
    module=sys.modules[__name__],
    symbol="TensorLike",
)(Union["tripy.Tensor", "tripy.types.NestedNumberSequence"])

TensorLike.__doc__ = """
Type annotation for a parameter that is either a Tripy `Tensor` or a Python sequence that can be automatically converted into one.
"""