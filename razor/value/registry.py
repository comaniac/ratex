# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Value registry."""
# pylint: disable=invalid-name
from mnm._lib import _APIS, _get_apis

# Reload APIs to ensure functions from razor are included
_APIS = _get_apis()

ValueToHandle = _APIS.get("mnm.value.ValueToHandle", None)
HandleToValue = _APIS.get("mnm.value.HandleToValue", None)