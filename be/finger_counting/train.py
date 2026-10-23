import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader

from dataset import FingerDataset, train_transforms, valid_transforms
from model import FingerCNN

#http://kaggle.com/datasets/koryakinp/fingers/data 

def main():
    batch_size = 32
    learning_rate = 0.01
    num_epochs = 20
    
    if torch.cuda.is_available():
        device = torch.device('cuda')
    elif torch.backends.mps.is_available():
        device = torch.device('mps')
    else:
        device = torch.device('cpu')
    print(f"Training on device: {device}")

    #dataset load
    train_dataset = FingerDataset(root_dir='data/train', transform=train_transforms)
    valid_dataset = FingerDataset(root_dir='data/valid', transform=valid_transforms)

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    valid_loader = DataLoader(valid_dataset, batch_size=batch_size, shuffle=False)

    model = FingerCNN().to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.SGD(model.parameters(), lr=learning_rate)

    # 5. Training Loop
    total_steps = len(train_loader)
    
    for epoch in range(num_epochs):
        model.train() # Set model to training mode
        running_loss = 0.0
        
        for i, (images, labels) in enumerate(train_loader):
            images = images.to(device)
            labels = labels.to(device)
            
            outputs = model(images)
            loss = criterion(outputs, labels)
            
            optimizer.zero_grad() 
            loss.backward()       
            optimizer.step()     
            
            running_loss += loss.item()
            
            if (i+1) % 100 == 0:
                print(f"Epoch [{epoch+1}/{num_epochs}], Step [{i+1}/{total_steps}], Loss: {loss.item():.4f}")

        #validation
        model.eval() 
        correct = 0
        total = 0
        
        with torch.no_grad():
            for images, labels in valid_loader:
                images = images.to(device)
                labels = labels.to(device)
                
                outputs = model(images)
                _, predicted = torch.max(outputs.data, 1)
                
                total += labels.size(0)
                correct += (predicted == labels).sum().item()
                
        accuracy = 100 * correct / total
        print(f"Epoch [{epoch+1}/{num_epochs}] completed. Validation Accuracy: {accuracy:.2f}%")
        print("-" * 50)

    #model done
    torch.save(model.state_dict(), 'finger_cnn_model.pth')
    print("Training complete. Model saved to 'finger_cnn_model.pth'.")

if __name__ == '__main__':
    main()