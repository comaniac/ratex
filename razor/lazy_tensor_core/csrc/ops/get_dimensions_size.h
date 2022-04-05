/*
 * Copyright (c) 2018 Google Inc. All Rights Reserved.
 * SPDX-License-Identifier: BSD-3-Clause
 * Modifications Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

#pragma once

#include <vector>

#include "lazy_tensor_core/csrc/ir.h"

namespace torch_lazy_tensors {
namespace ir {
namespace ops {

class GetDimensionsSize : public Node {
 public:
  GetDimensionsSize(const Value& input, std::vector<int64_t> dimensions);

  NodePtr Clone(OpList operands) const override;

  std::string ToString() const override;

  const std::vector<int64_t>& dimensions() const {
    return dimensions_;
  }

 private:
  std::vector<int64_t> dimensions_;
};

}  // namespace ops
}  // namespace ir
}  // namespace torch_lazy_tensors
