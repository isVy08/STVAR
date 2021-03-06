import os, sys, math
from utils import *
import pandas as pd
import torch.nn as nn
from tqdm import tqdm
from torch.utils.data import DataLoader


threshold = None if sys.argv[4] == 'None' else int(sys.argv[4])


def generate_data(X, p):
    T = X.size(1)
    input = []
    target = []
    for i in range(p, T):
        target.append(X[:, i])
        input.append(X[:, i-p:i])
    return torch.stack(input), torch.stack(target)

class Model(nn.Module):
    def __init__(self, input_size):
        super(Model, self).__init__()

        self.N = input_size

        # Define parameters
        weights = torch.empty(input_size * input_size, 1)
        self.weights = nn.Parameter(nn.init.xavier_normal_(weights)) # 0.015

    def forward(self, x, g):
        
        g.requires_grad = False
        if g.type() == 'torch.sparse.FloatTensor':
            f = torch.sparse.mm(g, self.weights ** 2)
        else:
            f = torch.matmul(g, self.weights ** 2) # [N ** 2, T]
        
        w = f.reshape(self.N, self.N) 
        w = torch.softmax(w, -1) # add minus sign if increasing
        z = w @ x
        z = z.sum(-1)
        return z, f




def train(X, d, p, batch_size, epochs, lr, model_path, shape, device='cpu'):
    
    device = torch.device(device if torch.cuda.is_available() else 'cpu')
    
    # q is q-quantile value, if q is None, compute order statistics instead
    g = basis_function(d, shape, q = threshold) 
    g = torch.from_numpy(g).float()
    
    if threshold is not None and threshold < 200:
        g = g.to_sparse()
    
    N, T = X.shape   
    V = 50
    
    model = Model(N)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    if os.path.isfile(model_path):
        load_model(model, optimizer, model_path, device)
    else:
        model.to(device)
    
    model.to(device)
    loss_fn = nn.MSELoss()

    tloss = vloss = 1e+10


    # Generate data 
    input, target = generate_data(X, p)
    loader = DataLoader(list(range(T-p-V)), batch_size=batch_size, shuffle=True)

    for epoch in range(1, epochs + 1):
        train_losses = 0
        val_losses = 0
        for idx in tqdm(loader): 
            y = target[idx,]
            x = input[idx, ]
            pred, _ = model(x, g)
            pred = pred.squeeze(-1)
            optimizer.zero_grad()
            loss = loss_fn(pred, y)
            loss.backward()
                        
            optimizer.step()
            train_losses += loss.item()
            
        pred, _ = model(input[-V:, ], g)
        pred = pred.squeeze(-1)
        val_loss = loss_fn(pred, target[-V:, ])
            
        train_loss = train_losses / len(loader)
        msg = f"Epoch: {epoch}, Train loss: {train_loss:.5f}, Val loss: {val_loss:.5f}"
        print(msg)        
        
        if train_loss < tloss and val_loss <= vloss:
            print('Saving model ...')
            torch.save({'model_state_dict': model.state_dict(),'optimizer_state_dict': optimizer.state_dict(),}, model_path)
            tloss = train_loss
            vloss = val_loss
        

def forecast(X, d, p, model_path, forecast_path, shape, device='cpu'):

    g = basis_function(d, shape, q = threshold)
    g = torch.from_numpy(g).float()
    g = g.to_sparse()
    
    
    #  Intialize model
    N, T = X.shape 
    loss_fn = nn.MSELoss()
    model = Model(N)
    load_model(model, None, model_path, device)

    Xts = torch.from_numpy(X).float()
    input, target = generate_data(Xts, p)
    
    
    print('Predicting ...')
    pred, F = model(input, g)
    pred = pred.squeeze(-1)
    loss = loss_fn(pred, target)
 
    pred = torch.t(pred)
    out = torch.cat((Xts[:, :p], pred), dim=-1)
    print(loss.item())
    
    out = out.detach().numpy()
    
    F = F.detach().numpy()
    write_pickle([X, out, F], forecast_path) 
    
    


if __name__ == "__main__":

    sample_path = 'data/sample.pickle'
    data_path = sys.argv[1]
    forecast_path = sys.argv[2]
    model_path = sys.argv[3]
    
    
    df = pd.read_csv(data_path)
    X = df.iloc[:, 1:].to_numpy()

    train_size = 300
    batch_size = 50
    epochs = 100
    lr = 0.01
    
    p = 1

    _, d = load_pickle(sample_path)
                
    X_train = X[:, :train_size]  
    X_train = torch.from_numpy(X_train).float()

    shape = 'convex_dec'

    train(X_train, d, p, batch_size, epochs, lr, model_path, shape, device='cpu')
    forecast(X, d, p, model_path, forecast_path, shape)





