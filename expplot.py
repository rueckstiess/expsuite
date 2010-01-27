from expsuite import ExperimentSuite
from matplotlib import pyplot as plt
from numpy import *
import time
import optparse


def creategraphs():
    for i, exp in enumerate(experiments):
        plt.subplot(shape, shape, i+1)

        hgraphs[exp] = []
        params = suite.read_params(exp)
            
        for r in range(params['repetitions']):
            h = suite.get_history(exp, r, 'return')
            # if h != []:
            hgraphs[exp].append(plt.plot(h, color='gray')[0])

        plt.title(exp)
        plt.gcf().canvas.draw()



def parse_opt():
    """ parses the command line options for different settings """
    optparser = optparse.OptionParser()
    # optparser.add_option('-c', '--config',
    #     action='store', dest='config', type='string', default='experiments.cfg', 
    #     help="your experiments config file")
    # optparser.add_option('-n', '--numcores',
    #     action='store', dest='ncores', type='int', default=cpu_count(), 
    #     help="number of processes you want to use, default is %i"%cpu_count())  
    # optparser.add_option('-d', '--del',
    #     action='store_true', dest='delete', default=False, 
    #     help="delete experiment folder if it exists")
    # optparser.add_option('-p', '--progress',
    #     action='store_true', dest='progress', default=False, 
    #     help="observe progress of the experiments interactively")
    # optparser.add_option('-b', '--browse',
    #     action='store_true', dest='browse', default=False, 
    #     help="browse experiments in config file.")      
    # optparser.add_option('-B', '--Browse',
    #     action='store_true', dest='browse_big', default=False, 
    #     help="browse experiments in config file, more verbose than -b")      
    
    optparser.add_option('-e', '--experiment',
        action='append', dest='experiments', type='string', 
        help="experiment to include in plot, default is all experiments.")      

    options, args = optparser.parse_args()
    return options, args

if __name__ == '__main__':
    
    options, args = parse_opt()
    
    suite = ExperimentSuite()
    
    # get all experiments
    path = '.'
    if len(args) > 0:
        path = args[0]

    experiments = suite.get_exps(path)
    print options
    if options.experiments:
        experiments = [e for e in experiments if e.split('/')[2] in options.experiments]
    
    shape = ceil(sqrt(len(experiments)))
    hgraphs = {}

    plt.ion()
    plt.figure(figsize=(16,10))

    
    creategraphs()
    while True:
        for i, exp in enumerate(experiments):
            params = suite.read_params(exp)
            
            for r,p in enumerate(hgraphs[exp]):
                h = suite.get_history(exp, r, 'return')
                if h != []:
                    if len(h) > len(p.get_ydata()):
                        # new data point, draw line in red
                        p.set_color('red')
                    else:
                        p.set_color('gray')
                    
                    # set the new axis limits
                    plt.subplot(shape, shape, i+1)
                    l = plt.xlim()
                    plt.xlim(0, max(len(h)+1, l[1]))
                    l = plt.ylim()
                    plt.ylim(min(l[0], min(h)-0.1*abs(min(h))), max(l[1], max(h)+0.1*abs(max(h))))
                
                    p.set_xdata(range(len(h)))
                    p.set_ydata(list(h))

                    
        plt.gcf().canvas.draw()      
        time.sleep(3)

