import os
from PIL import Image
import torch
from torch.utils.data import Dataset, DataLoader
from torchvision.transforms import v2

# Custom Transform: Simulates cheap webcam sensors and low-light static
class AddGaussianNoise:
    def __init__(self, mean=0.0, std=0.2):
        self.std = std
        self.mean = mean
        
    def __call__(self, tensor):
        # Adds noise and clamps values to stay within valid [0, 1] image range
        noise = torch.randn(tensor.size()) * self.std + self.mean
        return torch.clamp(tensor + noise, 0.0, 1.0)

# Aggressive Training Transforms
train_transforms = v2.Compose([
    v2.ToImage(),
    
    # 1. Spatial Distortions: Webcams are rarely perfectly aligned
    v2.RandomHorizontalFlip(p=0.5), # Left hands become right hands, doubling diversity
    v2.RandomAffine(
        degrees=30,             # Rotate up to 30 degrees
        translate=(0.15, 0.15), # Shift off-center by 15%
        scale=(0.7, 1.2),       # Zoom in and out
        shear=15                # Skew the hand shape
    ),
    
    # 2. Lighting & Sensor Corruptions
    v2.ColorJitter(brightness=0.7, contrast=0.7), # Heavy lighting variations
    v2.RandomApply([v2.GaussianBlur(kernel_size=5, sigma=(0.1, 2.0))], p=0.3), # Motion/focus blur
    
    # Convert to Tensor [0.0, 1.0] before applying tensor-specific operations
    v2.ToDtype(torch.float32, scale=True),
    
    # 3. Noise & Occlusion: Forces the network to ignore missing data/backgrounds
    v2.RandomApply([AddGaussianNoise(mean=0.0, std=0.15)], p=0.5),
    v2.RandomErasing(
        p=0.5, 
        scale=(0.02, 0.25), 
        ratio=(0.3, 3.3), 
        value=0.5 # Drops random gray blocks onto the image to simulate background clutter
    ),
    
    # 4. Standardize
    v2.Normalize(mean=[0.5], std=[0.5])
])

# Test transforms remain clean (only scaling and normalizing)
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