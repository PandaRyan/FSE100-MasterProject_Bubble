import os
from PIL import Image
import torch
from torch.utils.data import Dataset, DataLoader
from torchvision.transforms import v2

# Define Torchvision V2 Transforms
train_transforms = v2.Compose([
    v2.ToImage(), # Converts PIL Image to tensor without scaling
    v2.RandomRotation(degrees=15),
    v2.ColorJitter(brightness=0.2, contrast=0.2),
    v2.ToDtype(torch.float32, scale=True), # Scales pixel values to [0.0, 1.0]
    v2.Normalize(mean=[0.5], std=[0.5]) # Grayscale normalization
])

valid_transforms = v2.Compose([
    v2.ToImage(),
    v2.ToDtype(torch.float32, scale=True),
    v2.Normalize(mean=[0.5], std=[0.5])
])

class FingerDataset(Dataset):
    def __init__(self, root_dir, transform=None):
        self.root_dir = root_dir
        self.transform = transform
        self.image_files = [f for f in os.listdir(root_dir) if f.endswith('.png')]

    def __len__(self):
        return len(self.image_files)

    def __getitem__(self, idx):
        img_name = self.image_files[idx]
        img_path = os.path.join(self.root_dir, img_name)
        
        # The dataset images are grayscale, but loading as L ensures 1 channel
        image = Image.open(img_path).convert("L")
        
        # Extract label from filename (e.g., '12345_4L.png' -> '4')
        # The label is the first character after the underscore
        label_str = img_name.split('_')[-1][0]
        label = int(label_str)
        
        if self.transform:
            image = self.transform(image)
            
        return image, label

# Test the loader if you run this file directly
if __name__ == "__main__":
    train_dataset = FingerDataset(root_dir='data/train', transform=train_transforms)
    train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
    
    # Fetch a single batch to verify
    images, labels = next(iter(train_loader))
    print(f"Image batch shape: {images.shape}") # Expected: [32, 1, 128, 128]
    print(f"Labels batch shape: {labels.shape}")
    print(f"First label: {labels[0]}")