#! /sw/bin/python2.6
# -*- coding: utf-8 -*-

#############################################################################
#
# ExperimentSuite
#
# Derive your experiment from the ExperimentSuite, fill in the reset() and
# iterate() methods, and define your defaults and experiments variables
# in a config file.
# ExperimentSuite will create directories, run the experiments and store the 
# logged data. An aborted experiment can be resumed at any time. If you want
# to resume it on iteration level (instead of repetition level) you need to
# implement the restore_state and save_state method and set the 
# restore_supported variable to True.
#
# Copyright 2009 - Thomas Rueckstiess
#
#############################################################################

from ConfigParser import ConfigParser
from multiprocessing import Process, Pool, cpu_count
from numpy import *
import os, sys, time, itertools, re, curses, optparse

def mp_runrep(args):
    return ExperimentSuite.run_rep(*args)

def progress(params, rep):
    name = params['name']
    fullpath = os.path.join(params['path'], params['name'])
    logname = os.path.join(fullpath, '%i.log'%rep)
    if os.path.exists(logname):
        logfile = open(logname, 'r')
        lines = logfile.readlines()
        logfile.close()
        return int(100 * len(lines) / params['iterations'])
    else: 
        return 0

def observe(paramlist):
    pad = curses.newpad(60, 90) 
    namelength = max([len(p['name']) for p in paramlist]) + 4
    
    while(True):
        for i, p in enumerate(paramlist):
            row = sum([pl['repetitions'] for pl in paramlist[:i]]) + i
            for r in range(p['repetitions']):
               prog = min(100, progress(p, r))
               pad.move(row, namelength)
               pad.clrtoeol()
               pad.addstr(row, 0, '%s %i'%(p['name'], r))
               pad.addstr(row, namelength, '|')
               pad.addstr(row, namelength + 50, '|')
               pad.addstr(row, namelength, '|'*(prog//2))
               pad.addstr(row, namelength + 53, '%3i%%'%prog)
               row += 1
               
        pad.refresh(0,0, 0,0, 20,90)
        time.sleep(1)

class ExperimentSuite(object):
    
    def __init__(self):
        self.parse_opt()
        self.parse_cfg()
        
        # change this in subclass, if you don't support restoring state on iteration level
        self.restore_supported = True
    
    def parse_opt(self):
        """ parses the command line options for different settings """
        optparser = optparse.OptionParser()
        optparser.add_option('-c', '--config',
            action='store', dest='config', type='string', default='experiments.cfg', 
            help="your experiments config file")
        optparser.add_option('-n', '--numcores',
            action='store', dest='ncores', type='int', default=cpu_count(), 
            help="number of processes you want to use, default is %i"%cpu_count())  
        optparser.add_option('-d', '--del',
            action='store_true', dest='delete', default=False, 
            help="delete experiment folder if it exists")
        optparser.add_option('-p', '--progress',
            action='store_true', dest='progress', default=False, 
            help="observe progress of the experiments interactively")
        optparser.add_option('-b', '--browse',
            action='store_true', dest='browse', default=False, 
            help="browse experiments in config file.")      
        optparser.add_option('-B', '--Browse',
            action='store_true', dest='browse_big', default=False, 
            help="browse experiments in config file, more verbose than -b")      

        options, args = optparser.parse_args()
        self.options = options
        return options, args
    
    def parse_cfg(self):
        """ parses the given config file for experiments """
        self.cfgparser = ConfigParser()
        self.cfgparser.read(self.options.config)
    
    def mkdir(self, path):
        """ create a directory if it does not exist. """
        if not os.path.exists(path):
            os.makedirs(path)
            
    def get_exps(self, path='.'):
        exps = []
        for dp, dn, fn in os.walk(path):
            if 'experiment.cfg' in fn:
                subdirs = [os.path.join(dp, d) for d in os.listdir(dp) if os.path.isdir(os.path.join(dp, d))]
                if all(map(lambda s: self.get_exps(s) == [], subdirs)):       
                    exps.append(dp)
        return exps
    
    def items_to_params(self, items):
        params = {}
        for t,v in items:       
            try:
                # try to evaluate parameter (float, int, list)
                # print dfgp.get(exp, o)
                params[t] = eval(v)
                if isinstance(params[t], ndarray):
                    params[t] = params[t].tolist()
            except (NameError, SyntaxError):
                # otherwise assume string
                params[t] = v
        return params        
           
    def read_params(self, exp, cfgname='experiment.cfg'):
        """ reads the parameters of the experiment (=path) given.
        """
        cfgp = ConfigParser()
        cfgp.read(os.path.join(exp, cfgname))
        section = cfgp.sections()[0]
        params = self.items_to_params(cfgp.items(section))
        params['name'] = section
        return params

    def find_exp(self, name, path='.'):
        exps = []
        for dp, dn, df in os.walk(path):
            if 'experiment.cfg' in df:
                cfgp = ConfigParser()
                cfgp.read(os.path.join(dp, 'experiment.cfg'))
                if name in cfgp.sections():
                    exps.append(dp)
        return exps
            
    
    def write_config_file(self, params, path):
        """ write a config file for this single exp in the folder path.
        """
        cfgp = ConfigParser()
        cfgp.add_section(params['name'])
        for p in params:
            if p == 'name':
                continue
            cfgp.set(params['name'], p, params[p])
        f = open(os.path.join(path, 'experiment.cfg'), 'w')
        cfgp.write(f)
        f.close()
                
    def get_history(self, exp, rep, tags):
        """ returns the whole history for one experiment and one repetition.
            tags can be a string or a list of strings. if tags is a string,
            the history is returned as list of values, if tags is a list of 
            strings or 'all', history is returned as a dictionary of lists
            of values.
        """
        params = self.read_params(exp)
           
        if params == None:
            raise SystemExit('experiment %s not found.'%exp)         
        
        # make list of tags, even if it is only one
        if tags != 'all' and not hasattr(tags, '__iter__'):
            tags = [tags] 
        
        results = {}
        logfile = os.path.join(exp, '%i.log'%rep)
        try:
            f = open(logfile)
        except IOError:
            if len(tags) == 1:
                return []
            else:
                return {}

        for line in f:
            pairs = line.split()
            for pair in pairs:
                tag,val = pair.split(':')
                if tags == 'all' or tag in tags:
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
            return results
            # raise ValueError('tag(s) not found: %s'%str(tags))
        if len(results) == 1:
            return results[results.keys()[0]]
        else:
            return results
    
    def get_value(self, exp, rep, tags, which='last'):
        """ Like get_history(..) but returns only one single value rather
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
        # distinguish dictionary (several tags) from list
        if type(history) == dict:
            for h in history:
                if which == 'last':
                    history[h] = history[h][-1]
                if which == 'min':
                    history[h] = min(history[h])
                if which == 'max':
                    history[h] = max(history[h])
                if type(which) == int:
                    history[h] = history[h][which]
            return history
            
        else:
            if which == 'last':
                return history[-1]
            if which == 'min':
                return min(history)
            if which == 'max':
                return max(history)
            if type(which) == int:
                return history[which]
            else: 
                return None
        
    def get_values_fix_params(self, exp, rep, tag, which='last', **kwargs):
        """ this function uses get_value(..) but returns all values where the
            subexperiments match the additional kwargs arguments. if alpha=1.0,
            beta = 0.01 is given, then only those experiment values are returned,
            as a list.
        """ 
        subexps = self.get_exps(exp)[1:]
        tagvalues = [re.sub("0+$", '0', '%s%f'%(k, kwargs[k])) for k in kwargs]
        
        values = [self.get_value(se, rep, tag, which) for se in subexps if all(map(lambda tv: tv in se, tagvalues))]
        params = [self.read_params(se) for se in subexps if all(map(lambda tv: tv in se, tagvalues))]
        
        return values, params
        
    
    def browse(self): 
        """ go through all subfolders (starting at '.') and return information
            about the existing experiments. if the -B option is given, all 
            parameters are shown, -b only displays the most important ones.
            this function does *not* execute any experiments.
        """
        for d in self.get_exps('.'):
            params = self.read_params(d)
            name = params['name']
            fullpath = os.path.join(params['path'], name)

            print '%16s %s'%('experiment', d)
                           
            try:
                minfile = min(
                    (os.path.join(dirname, filename)
                    for dirname, dirnames, filenames in os.walk(fullpath)
                    for filename in filenames
                    if filename.endswith(('.log', '.cfg'))),
                    key=lambda fn: os.stat(fn).st_mtime)
            
                maxfile = max(
                    (os.path.join(dirname, filename)
                    for dirname, dirnames, filenames in os.walk(fullpath)
                    for filename in filenames
                    if filename.endswith(('.log', '.cfg'))),
                    key=lambda fn: os.stat(fn).st_mtime)
            except ValueError:
                print '         started %s'%'not yet'
                
            else:      
                print '         started %s'%time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.stat(minfile).st_mtime))
                print '           ended %s'%time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.stat(maxfile).st_mtime))
            
            for k in ['repetitions', 'iterations']:
                print '%16s %s'%(k, params[k])   
            
            prog = 0
            for i in range(params['repetitions']):
                prog += progress(params, i)
            prog /= params['repetitions']
            
            print '%16s %i%%'%('progress', prog)
            
            if self.options.browse_big:
                # more verbose output
                for p in [p for p in params if p not in ('repetitions', 'iterations', 'path', 'name')]:
                    print '%16s %s'%(p, params[p])
                    
            print             

    
        
    
    def start(self):
        """ starts the experiments as given in the config file. """     
        
        # if -b or -B option is set, only show information, don't
        # start the experiments
        if self.options.browse or self.options.browse_big:
            self.browse()
            raise SystemExit
        
        # read main configuration file
        paramlist = []
        for exp in self.cfgparser.sections():
            params = self.items_to_params(self.cfgparser.items(exp))
            params['name'] = exp
            paramlist.append(params)
        
        # get all options that are iteratable and build all combinations (grid)
        iparamlist = []
        for params in paramlist:
            iterparams = [p for p in params if hasattr(params[p], '__iter__')]
            if len(iterparams) > 0:
                # write intermediate config file
                self.mkdir(os.path.join(params['path'], params['name']))
                self.write_config_file(params, os.path.join(params['path'], params['name']))
                
                # create sub experiments
                for il in itertools.product(*[params[p] for p in iterparams]):
                    par = params.copy()
                    par['name'] = par['name'] + '/' + re.sub("[' \[\],()]", '', str(zip(iterparams,[re.sub("0+$", '0', '%f'%i) for i in il])))
                    for i, ip in enumerate(iterparams):
                        par[ip] = il[i]
                    iparamlist.append(par)
            else:
                iparamlist.append(params)
        
        paramlist = iparamlist
        
        # create directories, write config files
        for pl in paramlist:
            # create experiment path and subdir
            fullpath = os.path.join(pl['path'], pl['name'])
            self.mkdir(fullpath)

            # delete old histories if --del flag is active
            if self.options.delete:
                os.system('rm %s/*' % fullpath)
         
            # write a config file for this single exp. in the folder
            self.write_config_file(pl, fullpath)
            
        # create experiment list 
        explist = []
            
        # expand paramlist for all repetitions and add self and rep number
        for p in paramlist:
            explist.extend(zip( [self]*p['repetitions'], [p]*p['repetitions'], xrange(p['repetitions']) ))
        
        if self.options.progress:
            # init ncurses
            stdscr = curses.initscr()
            curses.noecho()
            curses.cbreak()
            stdscr.keypad(1)
        
            p = Process(target=observe, args=(paramlist,))
            p.start()
        
        # if only 1 process is required call each experiment seperately (no worker pool)
        if self.options.ncores == 1:
            for e in explist:
                mp_runrep(e)
        else:
            # create worker processes    
            pool = Pool(processes=self.options.ncores)
            pool.map(mp_runrep, explist)
        
        if self.options.progress:
            # finalize ncurses
            p.terminate()
            curses.nocbreak()
            stdscr.keypad(0)
            curses.echo()
            curses.endwin()
        
        
    def run_rep(self, params, rep):
        """ run a single repetition including directory creation, log files, etc. """
        name = params['name']
        fullpath = os.path.join(params['path'], params['name'])
        logname = os.path.join(fullpath, '%i.log'%rep)
        # check if repetition exists and has been completed
        restore = 0
        if os.path.exists(logname):
            logfile = open(logname, 'r')
            lines = logfile.readlines()
            logfile.close()
            
            # if completed, continue loop
            if 'iterations' in params and len(lines) == params['iterations']:
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
            logfile = open(logname, 'a')
            self.restore_state(params, rep, restore)
        else:
            logfile = open(logname, 'w')
            
        # loop through iterations and call iterate
        for it in xrange(restore, params['iterations']):
            dic = self.iterate(params, rep, it)
            self.save_state(params, rep, it)
            # build string from dictionary
            outstr = ' '.join(map(lambda x: '%s:%s'%(x[0], str(x[1])), dic.items()))
            logfile.write(outstr + '\n')
            logfile.flush()
        logfile.close()
    
    
    def reset(self, params, rep):
        """ needs to be implemented by subclass """
        pass
    
    def iterate(self, params, rep, n):
        """ needs to be implemented by subclass """
        ret = {'iteration':n, 'rep':rep}
        return ret
    
    def save_state(self, params, rep, n):
        pass
        
    def restore_state(self, params, rep, n):
        """ if the experiment supports restarting within a repetition
            (on iteration level), return True and load necessary
            stored state in this function. Otherwise, restarting will
            be done on repetition level, deleting all unfinished
            repetitions and restarting the experiments.
        """
        pass
        
    
if __name__ == '__main__':
    es = ExperimentSuite()
    es.start()
    print es.get_values_fix_params('test1', 0, 'iteration', 'last', alpha=1.0)[0]
    print 'suite done.'
