# %% -------------------------------------------------------------------------------------------------------------------

# -------------------------------------
# Use a GRU to forecast a Chirp signal
# -------------------------------------

# %% --------------------------------------- Imports -------------------------------------------------------------------
import numpy as np
import tensorflow as tf
from scipy.signal import chirp
import matplotlib.pyplot as plt

# %% --------------------------------------- Set-Up --------------------------------------------------------------------
tf.random.set_seed(42)
np.random.seed(42)
PLOT_SIGNAL, PLOT_RESULT = False, True

# %% ----------------------------------- Hyper Parameters --------------------------------------------------------------
LR = 1e-3
N_EPOCHS = 5
BATCH_SIZE = 32
DROPOUT = 0
SEQ_LEN = 50
HIDDEN_SIZE = 16
STATEFUL = False
LOSS_WHOLE_SEQ = False

# %% -------------------------------------- GRU Class ------------------------------------------------------------------
class ChirpGRU(tf.keras.Model):
    def __init__(self, dropout=DROPOUT):
        super(ChirpGRU, self).__init__()
        self.gru = tf.keras.layers.GRU(units=HIDDEN_SIZE if HIDDEN_SIZE is not None else 1, dropout=dropout,
                                       batch_input_shape=(BATCH_SIZE, SEQ_LEN, 1) if STATEFUL else (None, SEQ_LEN, 1),
                                       return_sequences=True if LOSS_WHOLE_SEQ else False, stateful=STATEFUL)
        self.out = tf.keras.layers.Dense(1, activation="linear")
        self.training = True

    def call(self, x):
        gru_out = self.gru(x, training=self.training)
        if HIDDEN_SIZE:
            return self.out(gru_out)
        else:
            return gru_out

# %% -------------------------------------- Data Prep ------------------------------------------------------------------
time_steps = np.linspace(0, 10, 5000)
x = chirp(time_steps, f0=1, f1=0.1, t1=10, method='linear')
if PLOT_SIGNAL:
    plt.plot(time_steps, x)
    plt.show()
x_train, x_test = x[:int(0.75*len(x))], x[int(0.75*len(x)):]
x_train_prep = np.empty((len(x_train)-SEQ_LEN, SEQ_LEN, 1))
for idx in range(len(x_train)-SEQ_LEN):
    x_train_prep[idx, :, :] = x_train[idx:SEQ_LEN+idx].reshape(-1, 1)
x_test_prep = np.empty((len(x_test)-SEQ_LEN, SEQ_LEN, 1))
for idx in range(len(x_test)-SEQ_LEN):
    x_test_prep[idx, :, :] = x_test[idx:SEQ_LEN+idx].reshape(-1, 1)
x_train, x_test = tf.cast(tf.convert_to_tensor(x_train_prep), tf.float32), tf.cast(tf.convert_to_tensor(x_test_prep), tf.float32)
del x_train_prep, x_test_prep

# %% -------------------------------------- Training Prep ----------------------------------------------------------
model = ChirpGRU()
optimizer = tf.keras.optimizers.Adam(learning_rate=LR)
criterion = tf.keras.losses.MeanSquaredError()

train_loss = tf.keras.metrics.Mean(name='train_loss')
@tf.function
def train(x, y, loss_whole_seq=LOSS_WHOLE_SEQ):
    model.training = True
    with tf.GradientTape() as tape:
        pred = model(x)
        if loss_whole_seq:
            loss = criterion(y, pred)
        else:
            loss = criterion(y[:, -1], pred[:, -1])
    gradients = tape.gradient(loss, model.trainable_variables)
    optimizer.apply_gradients(zip(gradients, model.trainable_variables))
    train_loss(loss)

test_loss = tf.keras.metrics.Mean(name='test_loss')
@tf.function
def eval(x, y, loss_whole_seq=LOSS_WHOLE_SEQ):
    model.training = False
    pred = model(x)
    if loss_whole_seq:
        loss = criterion(y, pred)
    else:
        loss = criterion(y[:, -1], pred[:, -1])
    test_loss(loss)

# %% -------------------------------------- Training Loop ----------------------------------------------------------
print("Starting training loop...")
for epoch in range(N_EPOCHS):

    if STATEFUL:
        pass
    for batch in range(len(x_train) // BATCH_SIZE):
        inp_inds = slice(batch*BATCH_SIZE, (batch+1)*BATCH_SIZE)
        tar_inds = slice(batch * BATCH_SIZE + 1, (batch + 1) * BATCH_SIZE + 1)
        train(x_train[inp_inds], x_train[tar_inds])

    if STATEFUL:
        for batch in range(len(x_test) // BATCH_SIZE):
            inp_inds = slice(batch * BATCH_SIZE, (batch + 1) * BATCH_SIZE)
            tar_inds = slice(batch * BATCH_SIZE + 1, (batch + 1) * BATCH_SIZE + 1)
            eval(x_test[inp_inds], x_test[tar_inds])
    else:
        eval(x_test[:-1], x_test[1:])

    print("Epoch {} | Train Loss {:.5f} - Test Loss {:.5f}".format(epoch, train_loss.result(), test_loss.result()))
    train_loss.reset_states(); test_loss.reset_states()

# %% ------------------------------------------ Final Test -------------------------------------------------------------
if PLOT_RESULT:
    model.training = False
    if STATEFUL:
        if LOSS_WHOLE_SEQ:
            pred_train = np.empty((len(x_train)//BATCH_SIZE*BATCH_SIZE, SEQ_LEN, 1))
            pred_test = np.empty((len(x_test) // BATCH_SIZE * BATCH_SIZE, SEQ_LEN, 1))
        else:
            pred_train = np.empty((len(x_train) // BATCH_SIZE * BATCH_SIZE, 1))
            pred_test = np.empty((len(x_test) // BATCH_SIZE * BATCH_SIZE, 1))
        for batch in range(len(x_train) // BATCH_SIZE):
            inp_inds = slice(batch*BATCH_SIZE, (batch+1)*BATCH_SIZE)
            if LOSS_WHOLE_SEQ:
                pred_train[batch*BATCH_SIZE:(batch+1)*BATCH_SIZE, :, :] = model(x_train[inp_inds])
            else:
                pred_train[batch*BATCH_SIZE:(batch+1)*BATCH_SIZE, :] = model(x_train[inp_inds])
        for batch in range(len(x_test) // BATCH_SIZE):
            inp_inds = slice(batch * BATCH_SIZE, (batch + 1) * BATCH_SIZE)
            if LOSS_WHOLE_SEQ:
                pred_test[batch*BATCH_SIZE:(batch+1)*BATCH_SIZE, :, :] = model(x_test[inp_inds])
            else:
                pred_test[batch*BATCH_SIZE:(batch+1)*BATCH_SIZE, :] = model(x_test[inp_inds])
    else:
        pred_train = model(x_train).numpy()
        pred_test = model(x_test).numpy()
    if LOSS_WHOLE_SEQ:
        predictions_train, predictions_test = [], []
        for idx in range(len(pred_train)):
            predictions_train.append(pred_train[idx, -1].reshape(-1))
        for idx in range(len(pred_test)):
            predictions_test.append(pred_test[idx, -1].reshape(-1))
        pred_train, pred_test = np.array(predictions_train), np.array(predictions_test)
    plt.plot(time_steps, x, label="Real Time Series", linewidth=2)
    plt.plot(time_steps[SEQ_LEN:len(pred_train)+SEQ_LEN],
             pred_train, linestyle='dashed', label="Train Prediction")
    if STATEFUL:
        plt.scatter(time_steps[len(pred_train) + 2 * SEQ_LEN + BATCH_SIZE:-(
                len(x) - (len(pred_train) + 2 * SEQ_LEN + BATCH_SIZE) - len(pred_test))],
                    pred_test, color="y", label="Test Prediction")
    else:
        plt.scatter(time_steps[len(pred_train)+2*SEQ_LEN:],
                    pred_test, color="y", label="Test Prediction")
    plt.title("Chirp function with 1 Hz frequency at t=0 and 0.1 Hz freq at t=10\n"
              "LSTM predictions using the previous {} time steps".format(SEQ_LEN))
    plt.xlabel("Time"); plt.ylabel("Signal Intensity")
    plt.legend()
    plt.show()
