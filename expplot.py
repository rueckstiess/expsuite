from expsuite import ExperimentSuite
from matplotlib import pyplot as plt
from numpy import *
import time

suite = ExperimentSuite()


# get all experiments
experiments = suite.get_exps()
shape = ceil(sqrt(len(experiments)))
hgraphs = {}

plt.ion()
plt.figure(figsize=(16,10))


def creategraphs():
    for i, exp in enumerate(experiments):
        plt.subplot(shape, shape, i+1)

        hgraphs[exp] = []
        params = suite.read_params(exp)
            
        for r in range(params['repetitions']):
            h = suite.get_history(exp, r, 'return')
            # if h != []:
            hgraphs[exp].append(plt.plot(h, color='gray', alpha=0.5)[0])

        plt.title(exp)
        plt.gcf().canvas.draw()


if __name__ == '__main__':
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
                    print l, len(h), h
                    plt.ylim(min(l[0], min(h)-0.1*abs(min(h))), max(l[1], max(h)+0.1*abs(max(h))))
                
                    p.set_xdata(range(len(h)))
                    p.set_ydata(list(h))

                    
        plt.gcf().canvas.draw()   
        print 'x'    
        time.sleep(3)

