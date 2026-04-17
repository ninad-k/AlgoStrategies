"""
CNN Model — Simple convolutional neural network for chart pattern classification.
"""

import logging

logger = logging.getLogger(__name__)

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger.warning("PyTorch not installed. Run: pip install torch")

from .patterns import NUM_CLASSES


def get_model(image_size: int = 64) -> "PatternCNN":
    if not TORCH_AVAILABLE:
        raise ImportError("PyTorch required for pattern recognition")
    return PatternCNN(image_size=image_size, num_classes=NUM_CLASSES)


if TORCH_AVAILABLE:
    class PatternCNN(nn.Module):
        """
        Simple CNN for chart pattern recognition.

        Architecture:
            Conv2d(1,32) -> ReLU -> MaxPool
            Conv2d(32,64) -> ReLU -> MaxPool
            Conv2d(64,128) -> ReLU -> MaxPool
            Flatten -> FC(512) -> Dropout -> FC(num_classes)
        """

        def __init__(self, image_size: int = 64, num_classes: int = NUM_CLASSES):
            super().__init__()
            self.conv1 = nn.Conv2d(1, 32, kernel_size=3, padding=1)
            self.conv2 = nn.Conv2d(32, 64, kernel_size=3, padding=1)
            self.conv3 = nn.Conv2d(64, 128, kernel_size=3, padding=1)
            self.pool = nn.MaxPool2d(2, 2)
            self.dropout = nn.Dropout(0.3)

            # Calculate flattened size after 3 pool layers
            flat_size = 128 * (image_size // 8) * (image_size // 8)
            self.fc1 = nn.Linear(flat_size, 512)
            self.fc2 = nn.Linear(512, num_classes)

        def forward(self, x):
            x = self.pool(F.relu(self.conv1(x)))
            x = self.pool(F.relu(self.conv2(x)))
            x = self.pool(F.relu(self.conv3(x)))
            x = x.view(x.size(0), -1)
            x = self.dropout(F.relu(self.fc1(x)))
            x = self.fc2(x)
            return x
