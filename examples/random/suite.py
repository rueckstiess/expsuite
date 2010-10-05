from expsuite import PyExperimentSuite
from numpy import *
import os

class MySuite(PyExperimentSuite):
    
    restore_supported = True
    
    def reset(self, params, rep):
        # initialize array
        self.numbers = zeros(params['iterations'])
        
        # seed random number generator
        random.seed(params['seed'])
        
    def iterate(self, params, rep, n):
        # draw normally distributed random number
        self.numbers[n] = random.normal(params['mean'], params['std'])
        
        # calculate sample mean and offset
        samplemean = mean(self.numbers[:n+1])
        offset = abs(params['mean']-samplemean)
       
        # return dictionary
        ret = {'n':n, 'number':self.numbers[n], 
            'samplemean':samplemean, 'offset':offset}
        
        return ret
        
    def save_state(self, params, rep, n):
        # save array as binary file
        save(os.path.join(params['path'], params['name'], 
            'array_%i.npy'%rep), self.numbers)

    def restore_state(self, params, rep, n):
        # load array from file
        self.numbers = load(os.path.join(params['path'], 
            params['name'], 'array_%i.npy'%rep))
        

if __name__ == '__main__':
    mysuite = MySuite()
    mysuite.start()

