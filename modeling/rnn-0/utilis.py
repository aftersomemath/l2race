# -*- coding: utf-8 -*-
"""
Created on Fri Jun 19 08:28:34 2020

@author: Marcin
"""

import numpy as np
import torch
import torch.nn as nn
from torch.utils import data

from IPython.display import Image

import matplotlib.pyplot as plt

import pandas as pd
import os


def get_device():
    """
    Small function to correctly send data to GPU or CPU depending what is available
    """
    if torch.cuda.is_available():
        device = torch.device('cuda:0')
    else:
        device = torch.device('cpu')
    return device


class Sequence(nn.Module):
    """"
    Our RNN class.
    """

    def __init__(self, args):
        super(Sequence, self).__init__()
        """Initialization of an RNN instance"""

        # Check if GPU is available. If yes device='cuda:0' if not device='cpu'
        self.device = get_device()
        # Save args (default of from terminal line)
        self.args = args
        # Initialize RNN layers
        self.gru1 = nn.GRUCell(4, args.h1_size)  # RNN accepts 5 inputs: CartPole state (4) and control input at time t
        self.gru2 = nn.GRUCell(args.h1_size, args.h2_size)
        self.linear = nn.Linear(args.h2_size, 1)  # RNN out
        # Count data samples (=time steps)
        self.sample_counter = 0
        # Declaration of the variables keeping internal state of GRU hidden layers
        self.h_t = None
        self.h_t2 = None
        # Variable keeping the most recent output of RNN
        self.output = None
        # List storing the history of RNN outputs
        self.outputs = []

        # Send the whole RNN to GPU if available, otherwise send it to CPU
        self.to(self.device)

    def forward(self, predict_len: int, input, terminate=False):
        """
        Predicts future CartPole states IN "CLOSED LOOP"
        (at every time step prediction for the next time step is done based on CartPole state
        resulting from the previous prediction; only control input is provided from the ground truth at every step)
        """
        # From input to RNN (CartPole state + control input) get control input
        u_effs = input[:, :, :-1]
        # For number of time steps given in predict_len predict the state of the CartPole
        # At every time step RNN get as its input the ground truth value of control input
        # BUT instead of the ground truth value of CartPole state
        # it gets the result of the prediction for the last time step
        for i in range(predict_len):
            # Concatenate the previous prediction and current control input to the input to RNN for a new time step
            input_t = torch.cat((self.output, u_effs[self.sample_counter, :]), 1)
            # Propagate input through RNN layers
            self.h_t = self.gru1(input_t, self.h_t)
            self.h_t2 = self.gru2(self.h_t, self.h_t2)
            self.output = self.linear(self.h_t2)
            # Append the output to the outputs history list
            self.outputs += [self.output]
            # Count number of samples
            self.sample_counter = self.sample_counter + 1
            if i == 254:
                pass

        # if terminate=True transform outputs history list to a Pytorch tensor and return it
        # Otherwise store the outputs internally as a list in the RNN instance
        if terminate:
            self.outputs = torch.stack(self.outputs, 1)
            return self.outputs

    def reset(self):
        """
        Reset the network (not the weights!)
        """
        self.sample_counter = 0
        self.h_t = None
        self.h_t2 = None
        self.output = None
        self.outputs = []

    def initialize_sequence(self, input, train=True):

        """
        Predicts future CartPole states IN "OPEN LOOP"
        (at every time step prediction for the next time step is done based on the true CartPole state)
        """

        # If in training mode we will only run this function during the first several (args.warm_up_len) data samples
        # Otherwise we run it for the whole input
        if train:
            starting_input = input[:self.args.warm_up_len, :, :]
        else:
            starting_input = input

        # Initialize hidden layers
        self.h_t = torch.zeros(starting_input.size(1), self.args.h1_size, dtype=torch.float).to(self.device)
        self.h_t2 = torch.zeros(starting_input.size(1), self.args.h2_size, dtype=torch.float).to(self.device)

        # The for loop takes the consecutive time steps from input plugs them into RNN and save the outputs into a list
        # THE NETWORK GETS ALWAYS THE GROUND TRUTH, THE REAL STATE OF THE CARTPOLE, AS ITS INPUT
        # IT PREDICTS THE STATE OF THE CARTPOLE ONE TIME STEP AHEAD BASED ON TRUE STATE NOW
        for i, input_t in enumerate(starting_input.chunk(starting_input.size(0), dim=0)):
            self.h_t = self.gru1(input_t.squeeze(0), self.h_t)
            self.h_t2 = self.gru2(self.h_t, self.h_t2)
            self.output = self.linear(self.h_t2)
            self.outputs += [self.output]
            self.sample_counter = self.sample_counter + 1

        # In the train mode we want to continue appending the outputs by calling forward function
        # The outputs will be saved internally in the network instance as a list
        # Otherwise we want to transform outputs list to a tensor and return it
        if not train:
            self.outputs = torch.stack(self.outputs, 1)
            return self.outputs


def norm(x):
    m = np.mean(x)
    s = np.std(x)
    y = (x - m) / s
    return y


class Dataset(data.Dataset):
    def __init__(self, data, labels, args):
        'Initialization'
        self.data = data
        self.labels = labels
        self.args = args

        # Hyperparameters
        self.seq_len = args.exp_len_train  # Sequence length

    def __len__(self):

        'Total number of samples'

        # speed optimized, you only have to get sequencies
        return self.data.shape[0] - self.seq_len

    def __getitem__(self, idx):

        return self.data[idx:idx + self.seq_len, :], self.labels[idx:idx + self.seq_len]


def normalize(dat, mean, std):
    rep = int(dat.shape[-1] / mean.shape[
        0])  # there is 1 mean for each input sensor value, repeat it for each element in sequence in data
    mean = np.tile(mean, rep)
    std = np.tile(std, rep)
    dat = (dat - mean) / std
    return dat


def unnormalize(dat, mean, std):
    rep = int(dat.shape[-1] / mean.shape[0])  # results in cw_len to properly tile for applying to dat.
    # there is 1 mean for each input sensor value, repeat it for each element in sequence in data
    mean = np.tile(mean, rep)
    std = np.tile(std, rep)
    dat = dat * std + mean
    return dat

def save_normalization(save_path, tr_mean, tr_std, lab_mean, lab_std):
    fn_base = os.path.splitext(save_path)[0]
    print("\nSaving normalization parameters to " + str(fn_base)+'-XX.pt')
    norm = {
            'tr_mean': tr_mean,
            'tr_std': tr_std,
            'lab_mean': lab_mean,
            'lab_std': lab_std,
        }
    torch.save(norm, str(fn_base+'-norm.pt'))

def load_normalization(save_path):
    fn_base = os.path.splitext(save_path)[0]
    print("\nLoading normalization parameters from ", str(fn_base))
    norm = torch.load(fn_base+'-norm.pt')
    return norm['tr_mean'], norm['tr_std'], norm['lab_mean'], norm['lab_std']



def computeNormalization(dat: np.array):
    '''
    Computes the special normalization of our data
    Args:
        dat: numpy array of data arranged as [sample, sensor/control vaue]

    Returns:
        mean and std, each one is a vector of values
    '''
    # Collect desired prediction
    # All terms are weighted equally by the loss function (either L1 or L2),
    # so we need to make sure that we don't have values here that are too different in range
    # Since the derivatives are computed on normalized data, but divided by the delta time in ms,
    # we need to normalize the derivatives too. (We include the delta time to make more physical units of time
    # so that the values don't change with different sample rate.)
    m = np.mean(dat, 0)
    s = np.std(dat, 0)
    return m, s


def load_data(filepath, args, savepath, save_normalization_parameters=False):
    '''
    Loads dataset from CSV file
    Args:
        filepath: path to CSV file
        seq_len: number of samples in time input to RNN
        stride: step over data in samples between samples
        medfilt: median filter window, 0 to disable
        test_plot: test_plot.py file requires other way of loading data

    Returns:
        Unnormalized numpy arrays
        input_data:  indexed by [sample, sequence, # sensor inputs * cw_len]
        input dict:  dictionary of input data names with key index into sensor index value
        targets:  indexed by [sample, sequence, # output sensor values * pw_len]
        target dict:  dictionary of target data names with key index into sensor index value
        actual: raw input data indexed by [sample,sensor]
        actual dict:  dictionary of actual inputs with key index into sensor index value
        mean_features, std_features, mean_targets_data, std_targets_data: the means and stds of training and raw_targets data.
            These are vectors with length # of sensorss

        The last dimension of input_data and targets is organized by
         all sensors for sample0, all sensors for sample1, .....all sensors for sampleN, where N is the prediction length
    '''

    # Hyperparameters
    seq_len = args.exp_len_train  # Sequence length

    # Load dataframe
    print('loading data from ' + str(filepath))
    df = pd.read_csv(filepath, comment='#')

    print('processing data to generate sequences')
    time = df['time'].to_numpy()
    deltaTime = np.diff(time)
    deltaTime = np.insert(deltaTime, 0, 0)

    # Get Raw Data
    throttle = df['cmd.throttle'].to_numpy()
    brake = df['cmd.brake'].to_numpy()
    speed = df['speed'].to_numpy()

    # Actual Data for Plotting
    raw_actual = []
    raw_actual.append(time)
    raw_actual.append(deltaTime)
    raw_actual.append(throttle)
    raw_actual.append(brake)
    raw_actual.append(speed)
    # add to dict here to allow plotting more easily, don't forget other _dict above
    actual_dict = {'time': 0, 'deltaTime': 1, 'throttle': 2, 'brake': 3, 'speed': 4}

    # Features (Train Data)
    raw_features = []
    raw_features.append(deltaTime)
    raw_features.append(throttle)
    raw_features.append(brake)
    raw_features.append(speed)


    raw_features = np.vstack(raw_features).transpose()  # raw_features indexed by [sample, input sensor/control]
    # add to dict here to allow plotting more easily, don't forget other _dict below
    features_dict = {'deltaTime': 0, 'throttle': 1, 'brake': 2, 'speed': 3}

    # targetss (Label Data)
    raw_targets = []
    raw_targets.append(speed)
    raw_targets = np.vstack(raw_targets).transpose()  # raw_targets indexed by [sample, sensor]
    # add to dict here to allow plotting more easily, don't forget other _dict below
    targets_dict = {'speed': 0}

    # compute normalization of data now
    mean_features, std_features = computeNormalization(raw_features)
    mean_targets, std_targets = computeNormalization(raw_targets)

    if save_normalization_parameters:  # We only save normalization for train set - all the other sets we normalize withr respect to this set
        save_normalization(savepath, mean_features, std_features, mean_targets, std_targets)
        mean_train_features, std_train_features, mean_train_targets, std_train_targets = \
            mean_features, std_features, mean_targets, std_targets
    else:
        mean_train_features, std_train_features, mean_train_targets, std_train_targets \
            = load_normalization(savepath)

    raw_features = normalize(raw_features, mean_train_features, std_train_features)
    raw_targets = normalize(raw_targets, mean_train_targets, std_train_targets)

    # Shift by one so that rnn predicts one step ahead
    features = raw_features[:-1, ]
    targets = raw_targets[1:, ]

    return features, features_dict, targets, targets_dict, raw_actual, actual_dict, mean_features, std_features, mean_targets, std_targets


def plot_results(net, args, MyCart):
    """
    This function accepts RNN instance, arguments and CartPole instance.
    It runs one random experiment with CartPole,
    inputs the data into RNN and check how well RNN predicts CartPole state one time step ahead of time
    """
    # Reset the internal state of RNN cells, clear the output memory, etc.
    net.reset()

    # Generates ab CartPole  experiment and save its data
    test_set = Dataset(MyCart, args, train=False)  # Only experiment length is different for train=True/False

    # Format the experiment data
    # test_set[0] means that we take one random experiment, first on the list
    # The data will be however anyway generated on the fly and is in general not reproducible
    # TODO: Make data reproducable: set seed or find another solution
    features, targets = test_set[0]

    # Add empty dimension to fit the requirements of RNN input shape
    # (in fact we add dimension for batches - for testing we use only one batch)
    features = features.unsqueeze(0)

    # Convert Pytorch tensors to numpy matrices to inspect them - just for debugging purpose.
    # Variable explorers of IDEs are often not compatible with Pytorch format
    # features_np = features.detach().numpy()
    # targets_np = targets.detach().numpy()

    # Further modifying the input and output form to fit RNN requirements
    # If GPU available we send features to GPU
    if torch.cuda.is_available():
        features = features.float().cuda().transpose(0, 1)
        targets = targets.float()
    else:
        features = features.float().transpose(0, 1)
        targets = targets.float()

    # From features we extract control input and save it as a separate vector on the cpu
    u_effs = features[:, :, -1].cpu()
    # We shift it by one time step and double the last entry to keep the size unchanged
    u_effs = u_effs[1:]
    u_effs = np.append(u_effs, u_effs[-1])

    # Set the RNN in evaluation mode
    net = net.eval()
    # During several first time steps we let hidden layers adapt to the input data
    # train=False says that all the input should be used for initialization
    # -> we predict always only one time step ahead of time based on ground truth data
    predictions = net.initialize_sequence(features, train=False)

    # reformat the output of RNN to a form suitable for plotting the results
    # y_pred are prediction from RNN
    y_pred = predictions.squeeze().cpu().detach().numpy()
    # y_target are expected prediction from RNN, ground truth
    y_target = targets.squeeze().cpu().detach().numpy()

    # Get the time axes
    t = np.arange(0, y_target.shape[0]) * args.dt

    # Get position over time
    xp = y_pred[args.warm_up_len:, 0]
    xt = y_target[:, 0]

    # Get velocity over time
    vp = y_pred[args.warm_up_len:, 1]
    vt = y_target[:, 1]

    # get angle theta of the Pole
    tp = y_pred[args.warm_up_len:, 2] * 180.0 / np.pi  # t like theta
    tt = y_target[:, 2] * 180.0 / np.pi

    # Get angular velocity omega of the Pole
    op = y_pred[args.warm_up_len:, 3] * 180.0 / np.pi  # o like omega
    ot = y_target[:, 3] * 180.0 / np.pi

    # Create a figure instance
    fig, axs = plt.subplots(5, 1, figsize=(18, 14), sharex=True)  # share x axis so zoom zooms all plots

    # %matplotlib inline
    # Plot position
    axs[0].set_ylabel("Position (m)", fontsize=18)
    axs[0].plot(t, xt, 'k:', markersize=12, label='Ground Truth')
    axs[0].plot(t[args.warm_up_len:], xp, 'b', markersize=12, label='Predicted position')
    axs[0].tick_params(axis='both', which='major', labelsize=16)

    # Plot velocity
    axs[1].set_ylabel("Velocity (m/s)", fontsize=18)
    axs[1].plot(t, vt, 'k:', markersize=12, label='Ground Truth')
    axs[1].plot(t[args.warm_up_len:], vp, 'g', markersize=12, label='Predicted velocity')
    axs[1].tick_params(axis='both', which='major', labelsize=16)

    # Plot angle
    axs[2].set_ylabel("Angle (deg)", fontsize=18)
    axs[2].plot(t, tt, 'k:', markersize=12, label='Ground Truth')
    axs[2].plot(t[args.warm_up_len:], tp, 'c', markersize=12, label='Predicted angle')
    axs[2].tick_params(axis='both', which='major', labelsize=16)

    # Plot angular velocity
    axs[3].set_ylabel("Angular velocity (deg/s)", fontsize=18)
    axs[3].plot(t, ot, 'k:', markersize=12, label='Ground Truth')
    axs[3].plot(t[args.warm_up_len:], op, 'm', markersize=12, label='Predicted velocity')
    axs[3].tick_params(axis='both', which='major', labelsize=16)

    # Plot motor input command
    axs[4].set_ylabel("motor (N)", fontsize=18)
    axs[4].plot(t, u_effs, 'r', markersize=12, label='motor')
    axs[4].tick_params(axis='both', which='major', labelsize=16)

    # # Plot target position
    # axs[5].set_ylabel("position target", fontsize=18)
    # axs[5].plot(self.MyCart.dict_history['time'], self.MyCart.dict_history['PositionTarget'], 'k')
    # axs[5].tick_params(axis='both', which='major', labelsize=16)

    axs[4].set_xlabel('Time (s)', fontsize=18)

    plt.show()
    # Save figure to png
    fig.savefig('my_figure.png')
    Image('my_figure.png')
