# Python Experiment Suite

_PyExperimentSuite_ is an open source software tool written in Python, that supports scientists, engineers and others to conduct automated software experiments on a large scale with numerous different parameters.

It reads parameters (or ranges of parameters) from a configuration file, runs the experiments using multiple cores if desired and logs the results in files. Parameter combinations can be evaluated as a grid (each combination of parameters) or in a list (try several defined parameter combinations in row). _PyExperimentSuite_ also supports continuing any experiments where left off when the execution was interrupted (e.g. power failure, process was killed, etc.). The experiment results can be obtained in different ways by a built-in Python interface.

For more information, see the [documentation](./docs/documentation.pdf) for instructions.

## Installation

Install the `expsuite` package via pip:

```sh
pip install expsuite
```

## Basic Usage Example

Create a new Python file (e.g. `suite.py`) and define a class that inherits from `PyExperimentSuite`. Within the class, implement the two methods `reset()` and `iterate()`. Also add the main script execution code at the bottom (last 3 lines below).

```python
from expsuite import PyExperimentSuite

class MySuite(PyExperimentSuite):
    def reset(self, params, rep):
        """for this basic example, nothing needs to be loaded or initialized."""
        pass

    def iterate(self, params, rep, n):
        """this function does nothing but access the two parameters alpha and
        beta from the config file experiments.cfg and returns them for the
        log files, together with the current repetition and iteration number.
        """
        # access the two config file parameters alpha and beta
        alpha = params["alpha"]
        beta = params["beta"]

        # return current repetition and iteration number and the 2 parameters
        ret = {"rep": rep, "iter": n, "alpha": alpha, "beta": beta}
        return ret


if __name__ == "__main__":
    mysuite = MySuite()
    mysuite.start()
```

You also need an experiment config file. Create a second file `experiments.cfg` and add the following content:

```
[DEFAULT]
repetitions = 5
iterations = 10
path = results

[myexperiment]
alpha = 1
beta = 0.1
```

Now call the script with `python suite.py`.

It will have generated a local `./results` directory with one subdirectory `myexperiment` (the only experiment we defined in the config file). In this directory, you find 5 log files (`#.log` where `#` goes from 0 to 4) and another `experiments.cfg` file specific to this experiment.

For more examples, see the [examples](./examples/) folder.
