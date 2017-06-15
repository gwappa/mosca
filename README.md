# mosca: a minimal oscilloscope & data acquisition environment

'mosca' stands for *m*inimal *osc*illoscope and *a*cquisition environment.

The objective is to make an open-source environment that does something similar to Spike2;
that is, you can perform a continuous acquisition (and store it) _ad lib_ from multiple channels, possibly with some triggering and output options.

Right now it is coded primarily in Python (because of the usage of pyqtgraph), but not limited to this language.

It is still under rigorous development, and may have substantial changes in the codebase.

Currently, it does the followings:

+ Records from a selected set of analog input channels and scale them accordingly.
+ Displays the recorded data on an oscilloscope window.
+ Stores the recorded data in a binary file that one can later import as a numpy array.

Future plans include:

+ Make acquisitions available from DAQmx devices and Instrutech ITC-18.
+ More options on channel display & storage settings (as well as saving them).

# Requirements

+ Python 3.x
+ pyqtgraph (and everything it requires, such as numpy, Qt, PyQt etc.)

