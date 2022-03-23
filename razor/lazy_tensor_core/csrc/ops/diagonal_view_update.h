/*
 * Copyright (c) 2018 Google Inc. All Rights Reserved.
 * SPDX-License-Identifier: BSD-3-Clause
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

#pragma once

#include "lazy_tensor_core/csrc/ir.h"

namespace torch_lazy_tensors {
namespace ir {
namespace ops {

class DiagonalViewUpdate : public Node {
 public:
  DiagonalViewUpdate(const Value& target, const Value& input, int64_t offset, int64_t dim1,
                     int64_t dim2);

  NodePtr Clone(OpList operands) const override;

  std::string ToString() const override;

  int64_t offset() const {
    return offset_;
  }

  int64_t dim1() const {
    return dim1_;
  }

  int64_t dim2() const {
    return dim2_;
  }

 private:
  int64_t offset_;
  int64_t dim1_;
  int64_t dim2_;
};

}  // namespace ops
}  // namespace ir
}  // namespace torch_lazy_tensors
