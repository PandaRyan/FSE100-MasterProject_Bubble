import torch
import torch.nn as nn

class FingerCNN(nn.Module):
    def __init__(self):
        super(FingerCNN, self).__init__()
        
        self.features = nn.Sequential(
            #128 to 64
            nn.Conv2d(1, 16, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2, 2),
            
            #64 to 32
            nn.Conv2d(16, 32, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2, 2),
            
            #32 to 16
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2, 2)
        )
        
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(64 * 16 * 16, 128),
            nn.ReLU(),
            nn.Dropout(0.3), 
            nn.Linear(128, 6) 
        )

    def forward(self, x):
        x = self.features(x)
        x = self.classifier(x)
        return x