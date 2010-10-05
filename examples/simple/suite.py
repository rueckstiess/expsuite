from expsuite import PyExperimentSuite

class MySuite(PyExperimentSuite):
    
    def reset(self, params, rep):
        """ for this simple example, nothing needs to be loaded or initialized."""
        pass
        
    def iterate(self, params, rep, n):
        """ this function does nothing but access the two parameters alpha and
            beta from the config file experiments.cfg and return them for the 
            log files, together with the current repetition and iteration number.
        """
        # access the two config file parameters alpha and beta
        alpha = params['alpha']
        beta = params['beta']
        
        # return current repetition and iteration number and the 2 parameters
        ret = {'rep':rep, 'iter':n, 'alpha':alpha, 'beta':beta}
        return ret        

if __name__ == '__main__':
    mysuite = MySuite()
    mysuite.start()

