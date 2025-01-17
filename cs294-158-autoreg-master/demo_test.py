
# Demo 2

from tqdm import tqdm
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim

from deepul_helper.data import load_demo_2
from deepul_helper.utils import to_one_hot
from deepul_helper.visualize import plot_2d_dist, plot_train_curves

SEED = 1
np.random.seed(SEED)
torch.manual_seed(SEED)

device = torch.device('cuda')
n_train, n_test, d = 10000, 2500, 25
loader_args = dict(batch_size=128, shuffle=True)
train_loader, test_loader = load_demo_2(n_train, n_test, d, loader_args, visualize=True)

def train(model, train_loader, optimizer):
    model.train()
    train_losses = []
    for x in train_loader:
        x = x.to(device)
        loss = model.nll(x)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        train_losses.append(loss.item())

    return np.mean(train_losses[-50:])

def eval(model, data_loader):
    model.eval()
    total_loss = 0
    with torch.no_grad():
        for x in data_loader:
            x = x.to(device)
            loss = model.nll(x)
            total_loss += loss * x.shape[0]
        avg_loss = total_loss / len(data_loader.dataset)
    return avg_loss.item()

def train_epochs(model, train_loader, test_loader, train_args):
    epochs, lr = train_args['epochs'], train_args['lr']
    optimizer = optim.Adam(model.parameters(), lr=lr)

    pbar = tqdm(total=epochs)
    train_losses, test_losses = [], []
    for epoch in range(epochs):
        train_loss = train(model, train_loader, optimizer)
        test_loss = eval(model, test_loader)

        train_losses.append(train_loss)
        test_losses.append(test_loss)

        pbar.update(1)
        pbar.set_description(f'Train Loss {train_loss:.4f}, Test Loss {test_loss:.4f}')
    pbar.close()

    plot_2d_dist(model.get_dist())
    plot_train_curves(epochs, train_losses, test_losses, title='Training Curve')


class SimpleAutoregModel(nn.Module):

    def __init__(self):
        super().__init__()
        self.logits_x0 = nn.Parameter(torch.zeros(d), requires_grad=True)
        self.cond_x1 = nn.Sequential(
            nn.Linear(d, 200),
            nn.ReLU(),
            nn.Linear(200, 200),
            nn.ReLU(),
            nn.Linear(200, 200),
            nn.ReLU(),
            nn.Linear(200, d)
        )

    def nll(self, x):
        batch_size = x.shape[0]
        x0, x1 = x[:, 0], x[:, 1],

        # Loss for x0
        logits_x0 = self.logits_x0.unsqueeze(0).repeat(batch_size, 1)
        nll_x0 = F.cross_entropy(logits_x0, x0.long())

        # Loss for x1 | x0
        x0_onehot = to_one_hot(x0.long(), d, device)
        logits_x1 = self.cond_x1(x0_onehot)
        nll_x1 = F.cross_entropy(logits_x1, x1.long())

        return nll_x0 + nll_x1

    def get_dist(self):
        with torch.no_grad():
            x0 = torch.flip(torch.arange(d), [0]).to(device)
            x0 = to_one_hot(x0, d, device)

            log_prob_x1 = F.log_softmax(self.cond_x1(x0), dim=1)
            log_prob_x0 = F.log_softmax(self.logits_x0, dim=0).unsqueeze(1)
            log_prob = log_prob_x0 + log_prob_x1
            return log_prob.exp().cpu().numpy()


model = SimpleAutoregModel().to(device)
train_epochs(model, train_loader, test_loader, dict(epochs=20, lr=1e-3))
