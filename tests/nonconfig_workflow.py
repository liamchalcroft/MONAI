# Copyright (c) MONAI Consortium
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

import torch

from monai.bundle import BundleWorkflow
from monai.data import DataLoader, Dataset
from monai.engines import SupervisedEvaluator
from monai.inferers import SlidingWindowInferer
from monai.networks.nets import UNet
from monai.transforms import (
    Activationsd,
    AsDiscreted,
    Compose,
    EnsureChannelFirstd,
    LoadImaged,
    SaveImaged,
    ScaleIntensityd,
)
from monai.utils import BundleProperty, set_determinism


class NonConfigWorkflow(BundleWorkflow):
    """
    Test class simulates the bundle workflow defined by Python script directly.

    """

    def __init__(self, filename, output_dir):
        super().__init__(workflow="inference")
        self.filename = filename
        self.output_dir = output_dir
        self._bundle_root = "will override"
        self._device = torch.device("cpu")
        self._network_def = None
        self._inferer = None
        self._preprocessing = None
        self._postprocessing = None
        self._evaluator = None

    def initialize(self):
        set_determinism(0)
        if self._preprocessing is None:
            self._preprocessing = Compose(
                [LoadImaged(keys="image"), EnsureChannelFirstd(keys="image"), ScaleIntensityd(keys="image")]
            )
        dataset = Dataset(data=[{"image": self.filename}], transform=self._preprocessing)
        dataloader = DataLoader(dataset, batch_size=1, num_workers=4)

        if self._network_def is None:
            self._network_def = UNet(
                spatial_dims=3,
                in_channels=1,
                out_channels=2,
                channels=[2, 2, 4, 8, 4],
                strides=[2, 2, 2, 2],
                num_res_units=2,
                norm="batch",
            )
        if self._inferer is None:
            self._inferer = SlidingWindowInferer(roi_size=(64, 64, 32), sw_batch_size=4, overlap=0.25)

        if self._postprocessing is None:
            self._postprocessing = Compose(
                [
                    Activationsd(keys="pred", softmax=True),
                    AsDiscreted(keys="pred", argmax=True),
                    SaveImaged(keys="pred", output_dir=self.output_dir, output_postfix="seg"),
                ]
            )

        self._evaluator = SupervisedEvaluator(
            device=self._device,
            val_data_loader=dataloader,
            network=self._network_def.to(self._device),
            inferer=self._inferer,
            postprocessing=self._postprocessing,
            amp=False,
        )

    def run(self):
        self._evaluator.run()

    def finalize(self):
        return True

    def _get_property(self, name, property):
        if name == "bundle_root":
            return self._bundle_root
        if name == "device":
            return self._device
        if name == "network_def":
            return self._network_def
        if name == "inferer":
            return self._inferer
        if name == "preprocessing":
            return self._preprocessing
        if name == "postprocessing":
            return self._postprocessing
        if property[BundleProperty.REQUIRED]:
            raise ValueError(f"unsupported property '{name}' is required in the bundle properties.")

    def _set_property(self, name, property, value):
        if name == "bundle_root":
            self._bundle_root = value
        elif name == "device":
            self._device = value
        elif name == "network_def":
            self._network_def = value
        elif name == "inferer":
            self._inferer = value
        elif name == "preprocessing":
            self._preprocessing = value
        elif name == "postprocessing":
            self._postprocessing = value
        elif property[BundleProperty.REQUIRED]:
            raise ValueError(f"unsupported property '{name}' is required in the bundle properties.")
