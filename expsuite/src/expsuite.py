#############################################################################
#
# PyExperimentSuite
#
# Derive your experiment from the PyExperimentSuite, fill in the reset() and
# iterate() methods, and define your defaults and experiments variables
# in a config file.
# PyExperimentSuite will create directories, run the experiments and store the
# logged data. An aborted experiment can be resumed at any time. If you want
# to resume it on iteration level (instead of repetition level) you need to
# implement the restore_state and save_state method and make sure the
# restore_supported variable is set to True.
#
# For more information, consult the included documentation.pdf file.
#
# Licensed under the modified BSD License. See LICENSE file in same folder.
#
# Copyright 2010 - Thomas Rueckstiess
#
#############################################################################

from configparser import ConfigParser
from multiprocessing import Pool, cpu_count
from numpy import *
import os, time, itertools, re, argparse, types

def mp_runrep(args):
    """Helper function to allow multiprocessing support."""
    return PyExperimentSuite.run_rep(*args)


def progress(params, rep):
    """Helper function to calculate the progress made on one experiment."""
    name = params["name"]
    fullpath = os.path.join(params["path"], params["name"])
    logname = os.path.join(fullpath, "%i.log" % rep)
    if os.path.exists(logname):
        logfile = open(logname, "r")
        lines = logfile.readlines()
        logfile.close()
        return int(100 * len(lines) / params["iterations"])
    else:
        return 0


def convert_param_to_dirname(param):
    """Helper function to convert a parameter value to a valid directory name."""
    if type(param) == bytes:
        return param
    else:
        return "".join(x for x in str(param) if x.isalnum() or x == "-")


def is_iterable(thing):
    return not isinstance(thing, str) and hasattr(thing, "__iter__")

class PyExperimentSuite(object):

    # change this in subclass, if you support restoring state on iteration level
    restore_supported = False

    def __init__(self, **kwargs):
        self.parse_opt(**kwargs)
        self.parse_cfg()

        # list of keys, that had to be renamed because they contained spaces
        self.key_warning_issued = []

    def parse_opt(self,
            config='experiments.cfg',
            numcores=cpu_count(),
            chunksize=None,
            delete=False,
            experiment=None,
            browse=False,
            browse_big=False,
            progress=False):
        """parses the command line options for different settings."""
        argparser = argparse.ArgumentParser()
        argparser.add_argument(
            "-c",
            "--config",
            action="store",
            dest="config",
            type=str,
            default=config,
            help="your experiments config file",
        )
        argparser.add_argument(
            "-n",
            "--numcores",
            action="store",
            dest="ncores",
            type=int,
            default=numcores,
            help="number of processes you want to use, default is %i" % cpu_count(),
        )
        argparser.add_argument(
            "--chunksize",
            action="store",
            default=chunksize,
            type=int,
            dest="chunksize",
            help="chunks submitted to the process pool"
        )
        argparser.add_argument(
            "-d",
            "--delete",
            action="store_true",
            dest="delete",
            default=delete,
            help="delete experiment folder if it exists",
        )
        argparser.add_argument(
            "-e",
            "--experiment",
            action="append",
            dest="experiments",
            type=str,
            default=experiment,
            help="run only selected experiments, by default run all experiments in config file.",
        )
        argparser.add_argument(
            "-b",
            "--browse",
            action="store_true",
            dest="browse",
            default=browse,
            help="browse existing experiments.",
        )
        argparser.add_argument(
            "-B",
            "--Browse",
            action="store_true",
            dest="browse_big",
            default=browse_big,
            help="browse existing experiments, more verbose than -b",
        )
        argparser.add_argument(
            "-p",
            "--progress",
            action="store_true",
            dest="progress",
            default=progress,
            help="like browse, but only shows name and progress bar",
        )

        make_list = lambda x: [x] if not isinstance(x,list) and x else x
        options, args = argparser.parse_known_args()
        options.experiments = make_list(options.experiments)
        self.options = options
        return options, args

    def parse_cfg(self):
        """parses the given config file for experiments."""
        self.cfgparser = ConfigParser()
        if not self.cfgparser.read(self.options.config):
            raise SystemExit("config file %s not found." % self.options.config)

    def mkdir(self, path):
        """create a directory if it does not exist."""
        if not os.path.exists(path):
            os.makedirs(path)

    def get_exps(self, path="."):
        """go through all subdirectories starting at path and return the experiment
        identifiers (= directory names) of all existing experiments. A directory
        is considered an experiment if it contains a experiment.cfg file.
        """
        exps = []
        for dp, dn, fn in os.walk(path):
            if "experiment.cfg" in fn:
                subdirs = [
                    os.path.join(dp, d)
                    for d in os.listdir(dp)
                    if os.path.isdir(os.path.join(dp, d))
                ]
                if all([self.get_exps(s) == [] for s in subdirs]):
                    exps.append(dp)
        return exps

    def items_to_params(self, items):
        """evaluate the found items (strings) to become floats, ints or lists."""
        params = {}
        for t, v in items:
            try:
                # try to evaluate parameter (float, int, list)
                if v in ["grid", "list"]:
                    params[t] = v
                else:
                    params[t] = eval(v)
                if isinstance(params[t], ndarray):
                    params[t] = params[t].tolist()
            except (NameError, SyntaxError):
                # otherwise assume string
                params[t] = v
        return params

    def get_params(self, exp, cfgname="experiment.cfg"):
        """reads the parameters of the experiment (= path) given."""
        cfgp = ConfigParser()
        cfgp.read(os.path.join(exp, cfgname))
        section = cfgp.sections()[0]
        params = self.items_to_params(cfgp.items(section))
        params["name"] = section
        return params

    def get_exp(self, name, path="."):
        """given an experiment name (used in section titles), this function
        returns the correct path of the experiment.
        """
        exps = []
        for dp, dn, df in os.walk(path):
            if "experiment.cfg" in df:
                cfgp = ConfigParser()
                cfgp.read(os.path.join(dp, "experiment.cfg"))
                if name in cfgp.sections():
                    exps.append(dp)
        return exps

    def write_config_file(self, params, path):
        """write a config file for this single exp in the folder path."""
        cfgp = ConfigParser()
        cfgp.add_section(params["name"])
        for p in params:
            if p == "name":
                continue
            cfgp[params["name"]][p] = str(params[p])
        f = open(os.path.join(path, "experiment.cfg"), "w")
        cfgp.write(f)
        f.close()

    def get_history(self, exp, rep, tags):
        """returns the whole history for one experiment and one repetition.
        tags can be a string or a list of strings. if tags is a string,
        the history is returned as list of values, if tags is a list of
        strings or 'all', history is returned as a dictionary of lists
        of values.
        """
        params = self.get_params(exp)

        if params == None:
            raise SystemExit("experiment %s not found." % exp)

        # make list of tags, even if it is only one
        if tags != "all" and not is_iterable(tags):
            tags = [tags]

        results = {}
        logfile = os.path.join(exp, "%i.log" % rep)
        try:
            f = open(logfile)
            keys = f.readline().strip('\n').split(',')
        except IOError:
            if len(tags) == 1:
                return []
            else:
                return {}

        for line in f:
            values = line.strip('\n').split(',')
            for tag, val in zip(keys,values):
                if tags == "all" or tag in tags:
                    if not tag in results:
                        try:
                            results[tag] = [eval(val)]
                        except (NameError, SyntaxError):
                            results[tag] = [val]
                    else:
                        try:
                            results[tag].append(eval(val))
                        except (NameError, SyntaxError):
                            results[tag].append(val)

        f.close()
        if len(results) == 0:
            if len(tags) == 1:
                return []
            else:
                return {}
            # raise ValueError('tag(s) not found: %s'%str(tags))
        if len(tags) == 1:
            return results[list(results.keys())[0]]
        else:
            return results

    def get_history_tags(self, exp, rep=0):
        """returns all available tags (logging keys) of the given experiment
        repetition.

        Note: Technically, each repetition could have different
        tags, therefore the rep number can be passed in as parameter,
        even though usually all repetitions have the same tags. The default
        repetition is 0 and in most cases, can be omitted.
        """
        history = self.get_history(exp, rep, "all")
        return list(history.keys())

    def get_value(self, exp, rep, tags, which="last"):
        """Like get_history(..) but returns only one single value rather
        than the whole list.
        tags can be a string or a list of strings. if tags is a string,
        the history is returned as a single value, if tags is a list of
        strings, history is returned as a dictionary of values.
        'which' can be one of the following:
            last: returns the last value of the history
             min: returns the minimum value of the history
             max: returns the maximum value of the history
               #: (int) returns the value at that index
        """
        history = self.get_history(exp, rep, tags)

        # empty histories always return None
        if len(history) == 0:
            return None

        # distinguish dictionary (several tags) from list
        if type(history) == dict:
            for h in history:
                if which == "last":
                    history[h] = history[h][-1]
                if which == "min":
                    history[h] = min(history[h])
                if which == "max":
                    history[h] = max(history[h])
                if type(which) == int:
                    history[h] = history[h][which]
            return history

        else:
            if which == "last":
                return history[-1]
            if which == "min":
                return min(history)
            if which == "max":
                return max(history)
            if type(which) == int:
                return history[which]
            else:
                return None

    def get_values_fix_params(self, exp, rep, tag, which="last", **kwargs):
        """this function uses get_value(..) but returns all values where the
        subexperiments match the additional kwargs arguments. if alpha=1.0,
        beta=0.01 is given, then only those experiment values are returned,
        as a list.
        """
        subexps = self.get_exps(exp)
        tagvalues = ["%s%s" % (k, convert_param_to_dirname(kwargs[k])) for k in kwargs]

        values = [
            self.get_value(se, rep, tag, which)
            for se in subexps
            if all([tv in se for tv in tagvalues])
        ]
        params = [
            self.get_params(se) for se in subexps if all([tv in se for tv in tagvalues])
        ]

        return values, params

    def get_histories_fix_params(self, exp, rep, tag, **kwargs):
        """this function uses get_history(..) but returns all histories where the
        subexperiments match the additional kwargs arguments. if alpha=1.0,
        beta = 0.01 is given, then only those experiment histories are returned,
        as a list.
        """
        subexps = self.get_exps(exp)
        tagvalues = [re.sub("0+$", "0", "%s%f" % (k, kwargs[k])) for k in kwargs]

        histories = [
            self.get_history(se, rep, tag)
            for se in subexps
            if all([tv in se for tv in tagvalues])
        ]
        params = [
            self.get_params(se) for se in subexps if all([tv in se for tv in tagvalues])
        ]

        return histories, params

    def get_histories_over_repetitions(self, exp, tags, aggregate):
        """this function gets all histories of all repetitions using get_history() on the given
        tag(s), and then applies the function given by 'aggregate' to all corresponding values
        in each history over all iterations. Typical aggregate functions could be 'mean' or
        'max'.
        """
        params = self.get_params(exp)

        # explicitly make tags list in case of 'all'
        if tags == "all":
            tags = list(self.get_history(exp, 0, "all").keys())

        # make list of tags if it is just a string
        if not is_iterable(tags):
            tags = [tags]

        results = {}
        for tag in tags:
            # get all histories
            histories = zeros((params["repetitions"], params["iterations"]))
            skipped = []
            for i in range(params["repetitions"]):
                try:
                    histories[i, :] = self.get_history(exp, i, tag)
                except ValueError:
                    h = self.get_history(exp, i, tag)
                    if len(h) == 0:
                        # history not existent, skip it
                        print(
                            (
                                "warning: history %i has length 0 (expected: %i). it will be skipped."
                                % (i, params["iterations"])
                            )
                        )
                        skipped.append(i)
                    elif len(h) > params["iterations"]:
                        # if history too long, crop it
                        print(
                            (
                                "warning: history %i has length %i (expected: %i). it will be truncated."
                                % (i, len(h), params["iterations"])
                            )
                        )
                        h = h[: params["iterations"]]
                        histories[i, :] = h
                    elif len(h) < params["iterations"]:
                        # if history too short, crop everything else
                        print(
                            (
                                "warning: history %i has length %i (expected: %i). all other histories will be truncated."
                                % (i, len(h), params["iterations"])
                            )
                        )
                        params["iterations"] = len(h)
                        histories = histories[:, : params["iterations"]]
                        histories[i, :] = h

            # remove all rows that have been skipped
            histories = delete(histories, skipped, axis=0)
            params["repetitions"] -= len(skipped)

            # calculate result from each column with aggregation function
            aggregated = zeros(params["iterations"])
            for i in range(params["iterations"]):
                aggregated[i] = aggregate(histories[:, i])

            # if only one tag is requested, return list immediately, otherwise append to dictionary
            if len(tags) == 1:
                return aggregated
            else:
                results[tag] = aggregated

        return results

    def browse(self):
        """go through subfolders starting at the path of the configuration file,
        and return information about the existing experiments.
        If the -B option is given, all parameters are shown, -b only displays the most important ones.
        This function does *not* execute any experiments.
        """
        for d in self.get_exps(self.cfgparser.defaults()['path']):
            params = self.get_params(d)
            name = params["name"]
            basename = name.split("/")[0]
            # if -e option is used, only show requested experiments
            if self.options.experiments and basename not in self.options.experiments:
                continue

            fullpath = os.path.join(params["path"], name)

            # calculate progress
            prog = 0
            for i in range(params["repetitions"]):
                prog += progress(params, i)
            prog /= params["repetitions"]

            # if progress flag is set, only show the progress bars
            if self.options.progress:
                bar = "["
                bar += "=" * int(prog / 4)
                bar += " " * int(25 - prog / 4)
                bar += "]"
                print(("%3i%% %27s %s" % (prog, bar, d)))
                continue

            print(("%16s %s" % ("experiment", d)))

            try:
                minfile = min(
                    (
                        os.path.join(dirname, filename)
                        for dirname, dirnames, filenames in os.walk(fullpath)
                        for filename in filenames
                        if filename.endswith((".log", ".cfg"))
                    ),
                    key=lambda fn: os.stat(fn).st_mtime,
                )

                maxfile = max(
                    (
                        os.path.join(dirname, filename)
                        for dirname, dirnames, filenames in os.walk(fullpath)
                        for filename in filenames
                        if filename.endswith((".log", ".cfg"))
                    ),
                    key=lambda fn: os.stat(fn).st_mtime,
                )
            except ValueError:
                print(("         started %s" % "not yet"))

            else:
                print(
                    (
                        "         started %s"
                        % time.strftime(
                            "%Y-%m-%d %H:%M:%S",
                            time.localtime(os.stat(minfile).st_mtime),
                        )
                    )
                )
                print(
                    (
                        "           ended %s"
                        % time.strftime(
                            "%Y-%m-%d %H:%M:%S",
                            time.localtime(os.stat(maxfile).st_mtime),
                        )
                    )
                )

            for k in ["repetitions", "iterations"]:
                print(("%16s %s" % (k, params[k])))

            print(("%16s %i%%" % ("progress", prog)))

            if self.options.browse_big:
                # more verbose output
                for p in [
                    p
                    for p in params
                    if p not in ("repetitions", "iterations", "path", "name")
                ]:
                    print(("%16s %s" % (p, params[p])))

            print()

    def expand_param_list(self, paramlist):
        """expands the parameters list according to one of these schemes:
        grid: every list item is combined with every other list item
        list: every n-th list item of parameter lists are combined
        """
        # for one single experiment, still wrap it in list
        if type(paramlist) == dict:
            paramlist = [paramlist]

        # get all options that are iteratable and build all combinations (grid) or tuples (list)
        iparamlist = []
        for params in paramlist:
            if "experiment" in params and params["experiment"] == "single":
                iparamlist.append(params)
            else:
                iterparams = [p for p in params if is_iterable(params[p])]
                if len(iterparams) > 0:
                    # write intermediate config file
                    self.mkdir(os.path.join(params["path"], params["name"]))
                    self.write_config_file(
                        params, os.path.join(params["path"], params["name"])
                    )

                    # create sub experiments (check if grid or list is requested)
                    if "experiment" in params and params["experiment"] == "list":
                        iterfunc = zip
                    elif ("experiment" not in params) or (
                        "experiment" in params and params["experiment"] == "grid"
                    ):
                        iterfunc = itertools.product
                    else:
                        raise SystemExit(
                            "unexpected value '%s' for parameter 'experiment'. Use 'grid', 'list' or 'single'."
                            % params["experiment"]
                        )

                    for il in iterfunc(*[params[p] for p in iterparams]):
                        par = params.copy()
                        converted = str(
                            list(
                                zip(iterparams, list(map(convert_param_to_dirname, il)))
                            )
                        )
                        par["name"] = (
                            par["name"] + "/" + re.sub("[' \[\],()]", "", converted)
                        )
                        for i, ip in enumerate(iterparams):
                            par[ip] = il[i]
                        iparamlist.append(par)
                else:
                    iparamlist.append(params)

        return iparamlist

    def create_dir(self, params, delete=False):
        """creates a subdirectory for the experiment, and deletes existing
        files, if the delete flag is true. then writes the current
        experiment.cfg file in the folder.
        """
        # create experiment path and subdir
        fullpath = os.path.join(params["path"], params["name"])
        self.mkdir(fullpath)

        # delete old histories if --del flag is active
        if delete:
            os.system("rm %s/*" % fullpath)

        # write a config file for this single exp. in the folder
        self.write_config_file(params, fullpath)

    def start(self):
        """starts the experiments as given in the config file."""

        # if -b, -B or -p option is set, only show information, don't
        # start the experiments
        if self.options.browse or self.options.browse_big or self.options.progress:
            self.browse()
            raise SystemExit

        # read main configuration file
        paramlist = []
        for exp in self.cfgparser.sections():
            if not self.options.experiments or exp in self.options.experiments:
                params = self.items_to_params(self.cfgparser.items(exp))
                params["name"] = exp
                paramlist.append(params)

        self.do_experiment(paramlist)

    def do_experiment(self, params):
        """runs one experiment programatically and returns.
        params: either parameter dictionary (for one single experiment) or a list of parameter
        dictionaries (for several experiments).
        """
        paramlist = self.expand_param_list(params)

        # create directories, write config files
        for pl in paramlist:
            # check for required param keys
            if (
                ("name" in pl)
                and ("iterations" in pl)
                and ("repetitions" in pl)
                and ("path" in pl)
            ):
                self.create_dir(pl, self.options.delete)
            else:
                print(
                    "Error: parameter set does not contain all required keys: name, iterations, repetitions, path"
                )
                return False

        # create experiment list
        explist = []

        # expand paramlist for all repetitions and add self and rep number
        for p in paramlist:
            explist.extend(
                list(
                    zip(
                        [self] * p["repetitions"],
                        [p] * p["repetitions"],
                        list(range(p["repetitions"])),
                    )
                )
            )

        # if only 1 process is required call each experiment seperately (no worker pool)
        if self.options.ncores == 1:
            for e in explist:
                mp_runrep(e)
        else:
            # create worker processes
            pool = Pool(processes=self.options.ncores)
            pool.map(mp_runrep, explist, chunksize=self.options.chunksize)

        return True

    def run_rep(self, params, rep):
        """run a single repetition including directory creation, log files, etc."""
        name = params["name"]
        fullpath = os.path.join(params["path"], params["name"])
        logname = os.path.join(fullpath, "%i.log" % rep)
        # check if repetition exists and has been completed
        restore = 0
        if os.path.exists(logname):
            logfile = open(logname, "r")
            lines = logfile.readlines()
            logfile.close()

            # if completed, continue loop
            if "iterations" in params and len(lines) == params["iterations"]:
                return False
            # if not completed, check if restore_state is supported
            if not self.restore_supported:
                # not supported, delete repetition and start over
                # print 'restore not supported, deleting %s' % logname
                os.remove(logname)
                restore = 0
            else:
                restore = len(lines)

        self.reset(params, rep)

        if restore:
            logfile = open(logname, "a")
            self.restore_state(params, rep, restore)
        else:
            logfile = open(logname, "w")

        # loop through iterations and call iterate
        for it in range(restore, params["iterations"]):
            dic = self.iterate(params, rep, it)
            if self.restore_supported:
                self.save_state(params, rep, it)

            # replace all spaces in keys with underscores
            for k in dic:
                if " " in k:
                    newk = k.replace(" ", "_")
                    dic[newk] = dic[k]
                    del dic[k]
                    # issue warning but only once per key
                    if k not in self.key_warning_issued:
                        print(
                            (
                                "warning: key '%s' contained spaces and was renamed to '%s'"
                                % (k, newk)
                            )
                        )
                        self.key_warning_issued.append(k)

            # Write the header onyl if logfile was not opened in append mode (logging already started)
            if logfile.tell() == 0:
                logfile.write(','.join(dic.keys()))
                logfile.write('\n')
            logfile.write(','.join(str(x) for x in dic.values()))
            logfile.write('\n')
            logfile.flush()
        logfile.close()

        self.finalize(params, rep)

    def reset(self, params, rep):
        """needs to be implemented by subclass."""
        pass

    def iterate(self, params, rep, n):
        """needs to be implemented by subclass."""
        ret = {"iteration": n, "repetition": rep}
        return ret

    def finalize(self, params, rep):
        """can be implemented by sublcass."""
        pass

    def save_state(self, params, rep, n):
        """optionally can be implemented by subclass."""
        pass

    def restore_state(self, params, rep, n):
        """if the experiment supports restarting within a repetition
        (on iteration level), load necessary stored state in this
        function. Otherwise, restarting will be done on repetition
        level, deleting all unfinished repetitions and restarting
        the experiments.
        """
        pass
