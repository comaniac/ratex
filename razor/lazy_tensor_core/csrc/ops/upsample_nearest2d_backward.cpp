/*
 * Copyright (c) 2018 Google Inc. All Rights Reserved.
 * SPDX-License-Identifier: BSD-3-Clause
 * Modifications Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

#include "lazy_tensor_core/csrc/ops/upsample_nearest2d_backward.h"

#include "absl/strings/str_join.h"
#include "lazy_tensor_core/csrc/compiler/node_lowering.h"
#include "lazy_tensors/computation_client/debug_macros.h"
#include "lazy_tensors/computation_client/util.h"

namespace torch_lazy_tensors {
namespace ir {
namespace ops {

UpsampleNearestBackward::UpsampleNearestBackward(const Value& input,
                                                 std::vector<int64_t> output_size,
                                                 std::vector<int64_t> input_size)
    : Node(ir::OpKind(at::aten::upsample_nearest2d_backward), {input},
           /*num_outputs=*/1, lazy_tensors::util::MHash(output_size, input_size)),
      output_size_(std::move(output_size)),
      input_size_(std::move(input_size)) {
  SetShapeDeferred([&]() { return compiler::NodeLowering::Get()->Infer(this); });
}

NodePtr UpsampleNearestBackward::Clone(OpList operands) const {
  return MakeNode<UpsampleNearestBackward>(operands.at(0), output_size_, input_size_);
}

std::string UpsampleNearestBackward::ToString() const {
  std::stringstream ss;
  ss << Node::ToString() << ", output_size=(" << absl::StrJoin(output_size_, ", ")
     << "), input_size=(" << absl::StrJoin(input_size_, ", ") << ")";
  return ss.str();
}

}  // namespace ops
}  // namespace ir
}  // namespace torch_lazy_tensors
