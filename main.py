
import os
import argparse
import torch
import torch.nn as nn
import torch.optim as optim
from torch.autograd import Variable

from asg.model import Net
from asg.logger import Logger
from asg.word2vec import Word2Vec
from asg.data import DataLoader

# Argument settings
parser = argparse.ArgumentParser(
    description='PyTorch Automated Storyboard Generator')
parser.add_argument('--epochs', type=int, default=2,
                    help='Number of epochs for training')
parser.add_argument('--learningrate', type=float,
                    default=0.01, help='Learning Rate. Default=0.01')
parser.add_argument('--seed', type=int, default=451,
                    help='Random seed. Default=451')
parser.add_argument('--report', type=int, default=200,
                    help='Rate of reporting images. Default=200')
opt = parser.parse_args()
# opt = parser.parse_args(([
#     '--epochs',
#     '10',
#     '--learningrate',
#     '0.01',
#     '--seed',
#     '451'
# ]))

Logger.log("Loading Word2Vec")
word2vec = Word2Vec()

Logger.log("Loading Network")
CUDA_AVAILABLE = torch.cuda.is_available()

torch.manual_seed(opt.seed)
if CUDA_AVAILABLE:
    torch.cuda.manual_seed(opt.seed)

def variable(target):
    """Convert tensor to a variable"""
    if CUDA_AVAILABLE:
        target = target.cuda()
    return Variable(target)


net = Net()
if CUDA_AVAILABLE:
    net = net.cuda()


net.number_one = variable(torch.FloatTensor([1]))


criterion = nn.CosineEmbeddingLoss()
optimizer = optim.SGD(net.parameters(), lr=opt.learningrate)


def train(epoch):
    epoch_loss = 0
    net.train()
    loader = DataLoader('train', word2vec, seed=epoch)
    for idx, (image, text, distance) in enumerate(loader):
        optimizer.zero_grad()

        image = variable(image)
        text = variable(text)
        target = variable(torch.FloatTensor([distance]))

        output_image_var, output_text_var = net(image, text)
        loss = criterion(output_image_var, output_text_var, target)
        epoch_loss += loss.data[0]
        loss.backward()
        optimizer.step()

        if idx % opt.report == 0:
            Logger.log("Epoch[{}]({}/{}): Loss: {:.4f}".format(epoch,
                                                               idx,
                                                               len(loader),
                                                               loss.data[0] * 1000))

    Logger.log("Epoch {} Complete: Avg. Loss: {:.4f}".format(
        epoch, 1000 * epoch_loss / len(loader)))


def test():
    epoch_loss = 0
    net.eval()
    loader = DataLoader('test', word2vec)
    for idx, (image, text, distance) in enumerate(loader):

        image = variable(image)
        text = variable(text)
        target = variable(torch.FloatTensor([distance]))

        output_image_var, output_text_var = net(image, text)
        loss = criterion(output_image_var, output_text_var, target)
        epoch_loss += loss.data[0]

        if idx % opt.report == 0:
            Logger.log("Current Avg. Test Loss: {:.4f}".format(
                1000 * epoch_loss / (idx + 1)))

        if idx > 2 * opt.report:
            break # large testing currently not useful

    Logger.log("Avg. Test Loss: {:.4f}".format(
        1000 * epoch_loss / len(loader)))


def checkpoint(epoch):
    model_out_path = os.path.join("models", "model_epoch_{}.pth".format(epoch))
    torch.save(net, model_out_path)
    Logger.log("Checkpoint saved to {}".format(model_out_path))

Logger.log("Starting ...")
for epoch in range(1, opt.epochs + 1):
    train(epoch)
    test()
    checkpoint(epoch)
