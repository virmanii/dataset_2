# Battery Cell Capacity-Fade Estimation from Impedance Spectra
You are given electrochemical impedance spectroscopy (EIS) magnitude spectra collected from lithium-ion cells during a calibration campaign. Each row corresponds to one cell measured at one point in its life. Your goal is to estimate the cell's capacity fade (`target`, in %) from its impedance spectrum.

## Data

`/app/data/train.csv`

Each row contains:

- `bin_0` ... `bin_119` — impedance magnitude measured at 120 log-spaced
  frequencies from 0.01 Hz to 10 kHz.
- `target` — capacity fade (%), determined independently via reference
  discharge capacity testing.

## Task

Build a model that predicts capacity fade from the impedance spectrum.

The training data were collected during a single calibration campaign, in one lab, on one instrument, over a period of time. The held-out evaluation data come from other labs, other instruments, other cell batches, and a wider range of cell ages, collected at different points in time.

As a result, characteristics of the measured spectra that appear predictive in the calibration data may not necessarily be caused by capacity fade
itself. Some patterns may instead reflect properties of the measurement setup or collection process.

Your objective is therefore **not simply to maximize performance on the training distribution**, but to build a model whose predictions continue to
be reliable when measurement conditions differ from those seen during training.

Before submitting, it is good practice to consider whether your model would make similar predictions if the testing conditions would change. This is checked directly during evaluation.

## Deliverable

Write `/app/result/utils.py` exposing a module-level object named `result` with a `predict` method.

```python
result.predict(df)
```

`df` will contain the columns `bin_0` ... `bin_119`.

The method must return one predicted capacity-fade value (in %) for each input row, preserving row order.

## Requirements

Your submitted `utils.py` should:

- depend only on `numpy` and `pandas` at prediction time;
- contain everything needed for inference inside the file (no external weight files, no network calls, no retraining at import time);
- expose a module-level object named `result` implementing `result.predict(df)`.

You may use any available libraries during your own experimentation and model development, but the submitted inference code must satisfy the
runtime requirements above.

## Evaluation

Evaluation measures prediction quality on held-out data collected under conditions that differ from the calibration data. Performance therefore
depends both on predictive accuracy and on the ability of the model to generalize across changes in measurement conditions. Submissions are also
compared against a simple constant-prediction baseline, and against a matched-pair probe that holds the true cell state fixed while varying only
incidental measurement conditions.
