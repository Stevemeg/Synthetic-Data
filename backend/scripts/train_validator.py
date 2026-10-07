import argparse
import logging
from pathlib import Path


def train_validator(data_dir, save_path):
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torchvision import datasets, models, transforms

    # Data augmentation and normalization for training
    data_transforms = transforms.Compose(
        [
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ]
    )

    # Load the dataset from the folder structure
    image_datasets = datasets.ImageFolder(data_dir, data_transforms)
    dataloaders = torch.utils.data.DataLoader(
        image_datasets, batch_size=4, shuffle=True, num_workers=0
    )
    if not len(image_datasets):
        raise ValueError("Training image directory is empty")
    if Path(save_path).exists():
        raise ValueError("Model output already exists")
    class_names = image_datasets.classes
    logging.info("validator_training_start classes=%s", len(class_names))

    # Load pre-trained ResNet18
    logging.info("loading_resnet18")
    model = models.resnet18(weights="IMAGENET1K_V1")
    num_ftrs = model.fc.in_features
    # Adjust output layer to match our 3 classes
    model.fc = nn.Linear(num_ftrs, len(class_names))

    device = torch.device("cpu")  # Use CPU for simplicity
    model = model.to(device)

    criterion = nn.CrossEntropyLoss()
    optimizer = optim.SGD(model.parameters(), lr=0.001, momentum=0.9)

    logging.info("training_validator epochs=10")
    for epoch in range(10):
        model.train()
        running_loss = 0.0
        for inputs, labels in dataloaders:
            inputs = inputs.to(device)
            labels = labels.to(device)

            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            running_loss += loss.item() * inputs.size(0)

        logging.info(
            "validator_epoch=%s average_loss=%.4f", epoch + 1, running_loss / len(image_datasets)
        )

    # Save the model state and the class names so we can check them later
    Path(save_path).parent.mkdir(parents=True, exist_ok=True)
    torch.save({"model_state": model.state_dict(), "classes": class_names}, save_path)
    logging.info("validator_training_complete")


def main():
    parser = argparse.ArgumentParser(
        description="Experimental offline image classifier training; not clinical validation."
    )
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    if not args.data_dir.is_dir():
        parser.exit(1, "Training image directory does not exist\n")
    train_validator(args.data_dir, args.output)


if __name__ == "__main__":
    main()
