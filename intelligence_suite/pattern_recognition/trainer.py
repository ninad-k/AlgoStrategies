"""
Trainer — Training pipeline for the pattern recognition CNN.
"""

import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader, TensorDataset
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

from .model import get_model


class PatternTrainer:
    def __init__(self, config: dict):
        self.config = config
        pr_cfg = config.get("pattern_recognition", {})
        self.image_size = pr_cfg.get("window_size", 64)
        self.model_dir = Path("pattern_recognition/saved_models")
        self.model_dir.mkdir(parents=True, exist_ok=True)

    def train(self, images: np.ndarray, labels: np.ndarray,
              epochs: int = 50, batch_size: int = 32,
              learning_rate: float = 0.001) -> dict:
        """
        Train the CNN on labeled chart images.

        Args:
            images: numpy array of shape (N, H, W), values 0-255
            labels: numpy array of shape (N,), integer class labels
            epochs: number of training epochs
            batch_size: batch size
            learning_rate: Adam learning rate

        Returns:
            dict with training history (loss, accuracy per epoch)
        """
        if not TORCH_AVAILABLE:
            return {"error": "PyTorch not installed"}

        # Normalize images to 0-1 and add channel dimension
        X = torch.FloatTensor(images).unsqueeze(1) / 255.0  # (N, 1, H, W)
        y = torch.LongTensor(labels)

        # Train/val split (80/20)
        n_train = int(len(X) * 0.8)
        train_dataset = TensorDataset(X[:n_train], y[:n_train])
        val_dataset = TensorDataset(X[n_train:], y[n_train:])

        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=batch_size)

        model = get_model(self.image_size)
        criterion = nn.CrossEntropyLoss()
        optimizer = optim.Adam(model.parameters(), lr=learning_rate)

        history = {"train_loss": [], "val_loss": [], "val_accuracy": []}

        for epoch in range(epochs):
            # Training
            model.train()
            train_loss = 0
            for batch_X, batch_y in train_loader:
                optimizer.zero_grad()
                outputs = model(batch_X)
                loss = criterion(outputs, batch_y)
                loss.backward()
                optimizer.step()
                train_loss += loss.item()

            avg_train_loss = train_loss / len(train_loader)

            # Validation
            model.eval()
            val_loss = 0
            correct = 0
            total = 0
            with torch.no_grad():
                for batch_X, batch_y in val_loader:
                    outputs = model(batch_X)
                    loss = criterion(outputs, batch_y)
                    val_loss += loss.item()
                    _, predicted = torch.max(outputs, 1)
                    total += batch_y.size(0)
                    correct += (predicted == batch_y).sum().item()

            avg_val_loss = val_loss / max(len(val_loader), 1)
            val_accuracy = correct / max(total, 1)

            history["train_loss"].append(round(avg_train_loss, 4))
            history["val_loss"].append(round(avg_val_loss, 4))
            history["val_accuracy"].append(round(val_accuracy, 4))

            if (epoch + 1) % 10 == 0:
                logger.info(
                    f"Epoch {epoch+1}/{epochs} | "
                    f"Train Loss: {avg_train_loss:.4f} | "
                    f"Val Loss: {avg_val_loss:.4f} | "
                    f"Val Acc: {val_accuracy:.2%}"
                )

        # Save model
        model_path = self.model_dir / "pattern_cnn.pth"
        torch.save(model.state_dict(), model_path)
        logger.info(f"Model saved to {model_path}")

        history["final_accuracy"] = history["val_accuracy"][-1] if history["val_accuracy"] else 0
        history["model_path"] = str(model_path)
        return history
