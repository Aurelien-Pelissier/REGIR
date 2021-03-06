import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import random
import copy
import uuid
import scipy.stats as stat
from math import log, gamma, exp, factorial, pi, sqrt, erf, atan
from scipy.special import gammainc
from scipy.interpolate import interp1d
import os,sys



def Exponential_rate(t,rate, alpha):
    return rate,0

def Weibull_rate(t,rate,alpha):
    #only works for alpha >= 1
    beta = (alpha) * (rate * gamma((alpha + 1)/(alpha)))**(alpha)
    rate = (t**(alpha-1))*beta
    d_rate = (alpha-1)*(t**(alpha-2))*beta
    return rate,d_rate


def Gamma_rate(t,rate,alpha):
    if alpha < 1 and t == 0:
        return 0
    #only works for alpha >= 1
    beta = alpha*rate
    pdf = (beta**alpha)*(t**(alpha-1))*exp(-beta*t)/gamma(alpha)
    cdf = gammainc(alpha,beta*t)
    rate = pdf/(1-cdf)
    d_pdf = (beta**alpha)/gamma(alpha) * ( (alpha-1)*(t**(alpha-2))*exp(-beta*t) - beta*(t**(alpha-1))*exp(-beta*t))
    if cdf == 0:
        d_rate = 0
    else:
        d_rate = rate**2 + d_pdf/(1-cdf)
    return rate,d_rate

def Gaussian_rate(t, rate, alpha):
    if alpha < 1 and t == 0:
        return 0
    #here, alpha is the ratio between std and mean
    sigma = 1/rate*alpha
    mu = 1/rate
    if t > mu + 7*sigma: #necessary as the precision of cdf calculation is not precise enough
        rate = (t-mu)/sigma**2
        d_rate = 1/sigma**2
    else:
        pdf = 1/(sigma*sqrt(2*pi)) * exp(-(1/2) * (t-mu)**2/(sigma**2))
        cdf = 1/2*(1+erf((t-mu)/(sigma*sqrt(2))))
        rate = pdf/(1-cdf)
        d_pdf = -1/(sigma*sqrt(2*pi)) * exp(-(1/2) * (t-mu)**2/(sigma**2)) *(t-mu)/(sigma**2)
        
        if cdf == 0:
            d_rate = 0
        else:
            d_rate = rate**2 + d_pdf/(1-cdf)
    return rate,d_rate

def Lognormal_rate(t, rate, alpha):
    #here, alpha is the ratio between std and mean
    sigma0 = 1/rate*alpha
    mu0 = 1/rate
    mu = log(mu0**2 / sqrt(mu0**2 + sigma0**2))
    sigma = sqrt(log(1+ sigma0**2/mu0**2))
    if t == 0:
        rate = 0
    else:
        pdf = 1/(t*sigma*sqrt(2*pi)) * exp(-(1/2) * (log(t)-mu)**2/(sigma**2))
        cdf = 1/2*(1+erf((log(t)-mu)/(sigma*sqrt(2))))
        rate = pdf/(1-cdf)
        
    return rate,0 #flemme de calculer pr linstant


def Cauchy_rate(t, rate,gam):
    mu = 1/rate
    #alternative parametrization with rate: t0 = 1/rate
    pdf = 1 / (pi*gam*(1 + ((t-mu)/gam)**2))
    cdf = (1/pi) * atan( (t-mu)/gam ) + 1/2
    rate = pdf/(1-cdf)
    d_pdf = -(1/(pi*gam)) * 1/((1 + ((t-mu)/gam)**2))**2*(1/gam)*(t-mu)
    if cdf == 0:
        d_rate = 0
    else:
        d_rate = rate**2 + d_pdf/(1-cdf)
    return rate,d_rate


class Reaction_channel():
    
    def __init__(self,param_simulation, rate=1, shape_param=1, distribution = 'Weibull', name='', reactants = [], products = [], transfer_identity = False):
        """ Fixed parameters """
        self.reactants = reactants #reactant list of str
        self.products = products #produect list of str
        self.rate = rate #reaction rate
        self.shape_param = shape_param #alpha shape parameter of Weibull distribution
        self.name = name
        self.distribution = distribution #distribution type ('Weibull, Gamma, Gaussian)
        self.transfer_identity = transfer_identity
        
        """ Variable parameters """
        self.wait_times = [] ##Store the waiting time for this reaction channel, only for plotting purposes
        
        
        """ Distribution specific parameters """
        
        if rate < 0:
            print(' Reaction %s:' % name)
            print('   Rate cannot be negative')
            sys.exit()
            
        elif rate == 0:
            self.distribution = 'Exponential'
            self.rate_function = Exponential_rate
        
        elif distribution.lower() in ['exponential', 'exp']:
            self.distribution = 'Exponential'
            self.rate_function = Exponential_rate
            
        elif distribution.lower() in ['weibull','weib']:
            self.rate_function = Weibull_rate
            if shape_param < 1:
                print(' Reaction %s:' % name)
                print('   Shape parameter < 1 for Weiull distribution is')
                print('   currently not supported in this implementation')
                print('   (Only non infinite rate at t=0 are supported)')
                sys.exit()
            if shape_param == 1:
                self.distribution = 'Exponential'
                self.rate_function = Exponential_rate
                
        elif distribution.lower() in ['gamma','gam']:
            self.rate_function = Gamma_rate
            if shape_param < 1:
                print(' Reaction %s:' % name)
                print('   Shape parameter < 1 for Gamma distribution is')
                print('   currently not supported in this implementation')
                print('   (Only non infinite rate at t=0 are supported)')
                sys.exit()
            if shape_param == 1:
                self.distribution = 'Exponential'
                self.rate_function = Exponential_rate
                
        elif distribution.lower() in ['gaussian', 'normal', 'norm']:
            self.rate_function = Gaussian_rate
            if shape_param <= 0:
                print(' Reaction %s:' % name)
                print('   Zero or negative variance for LogNormal is not supported')
                sys.exit()
                
        elif distribution.lower() in ['lognormal','lognorm']:
            self.rate_function = Lognormal_rate
            if shape_param <= 0:
                print(' Reaction %s:' % name)
                print('   Zero or negative variance for Lognorm is not supported')
                sys.exit()
                
        elif distribution.lower() in ['cauchy', 'cau']:
            self.rate_function = Cauchy_rate
            if shape_param <= 0:
                print(' Reaction %s:' % name)
                print('   Zero or negative variance for Gaussian is not supported')
                sys.exit()

        else:
            print('  Unsupported distribution: %s' % distribution)
            sys.exit()
            
        
        
class Reactant():
       
    def __init__(self, ID = None):
        
        """
        Store the individual properties of a reactant
        such as the time since their last reaction (t_start)
        or other relevant parameters
        """
        
        if ID is None:
            self.id = self.gen_uuid() #unique cell ID
        else:
            self.id = ID
            
    
    def gen_uuid(self):
        """
        Generate a 32char hex uuid to use as a key 
        for each cell in the sorted dictionary
    
        random = SystemRandom() # globally defined
    
        """
        return uuid.UUID(int=random.getrandbits(128),version=4).hex        
        
        
class Gillespie_simulation():
    
    def __init__(self, N_init, param, min_ratio = 10, print_warnings = False):
        self.param = param
        self.param.min_ratio = min_ratio
        self.param.print_warnings = print_warnings
        self.reaction_channel_list = []  #list of reaction chanels
        self.reactant_population_init = N_init
        
    def reinitialize_pop(self):
        """
        Reset the reactant population list to its initial parameters
        Note that the stored inter event times of each channel and not reset
        """
        self.reactant_population = self.reactant_population_init.copy() # dictionary with reactant name as key and population as value
        self.reactant_list, self.reactant_times = self.initialise_reactant_list(self.reactant_population, self.reaction_channel_list) # dictionary with reactant name as key and list of reactant as value 
        
    def initialise_reactant_list(self,N_init, reaction_channel_list):
        """
        Initialize Reactant list with a dynamic list of reactants
        
        Input:
            N_r1, N_r2, .. ,N_rk = N_init
        
        Output:
            dict of dict containing reactants for each reactant type:
            the dict contains the reactant ID as key and reactant object as value
            - reactant_list[r1] = contain list of reactant r1 (dictionary)
            - reactant_list[r2] = contain list of reactant r2 (dictionary)
                        ...
            - reactant_list[rk] = contain list of reactant rk (dictionary)
        """
        
        reactant_list = dict()
        reactant_times = dict()
        ci = 0
        for ri in N_init:
            react_i = []
            react_times_i = dict()
            
            for channel in reaction_channel_list:
                react_times_i[channel.name] = dict()
            
            if N_init[ri] > 0:
                
                for j in range(N_init[ri]):
                    new_reactant = Reactant()
                    react_i.append(new_reactant)
                    for channel in reaction_channel_list:
                        react_times_i[channel.name][new_reactant.id] = 0
                    
                    ci += 1
            reactant_list[ri] = react_i
            reactant_times[ri] = react_times_i
            
        return reactant_list, reactant_times
    
    
    def run_simulations(self, Tend, verbose = True, order = 1):
        """
        Run several Gillespie simulations and plot the results
        """        

        self.max_r0 = np.max([channel_i.rate for channel_i in self.reaction_channel_list])
        
        """Quick check if transfert ID = False for innapropriate reactions"""
        for channel_i in self.reaction_channel_list:
            if len(set(channel_i.products)) < len(channel_i.products):
                if channel_i.transfer_identity:
                    print("   WARNING: Setting transfer_identity to True for channels where products are")
                    print("            of the same kind is ambigious due to duplicated ID in the dictionary") 
                    sys.exit()
        
        population = np.empty((self.param.N_simulations, self.param.timepoints, len(self.reactant_population_init)+1))
        for ni in range(self.param.N_simulations):
            if verbose: print("   Simulation",ni+1,"/",self.param.N_simulations,"...")
            self.reinitialize_pop() #reset to initial conditions    
            self.run_simulation(Tend, order = order)
            #G_simul.plot_populations_single()
            #G_simul.plot_inter_event_time_distribution()
            population[ni,:,:] = self.get_populations()           
          
        self.population_compiled = population
        return population
        
    def run_simulation(self, Tend, order = 1):
        """
        Run Gillespie simulation until the final time is reached,
        or the total population surpass a given threshold (10k reactants).
        """
        
        timepoints = self.param.timepoints
        
        self.t = 0
        ti = 0
        self.Tend = Tend
        self.population_t = -np.ones((timepoints,len(self.reactant_population)+1))
        
        while self.t < Tend: #Monte Carlo step
        
            if self.t >= ti*Tend/timepoints: #record the populations
                self.population_t[ti,:-1] = list(self.reactant_population.values())
                ti = int(self.t/Tend*(timepoints))+1

            propensity, individual_rates = self.compute_propensities()
            a0 = np.sum(propensity)
            
            if a0 < 3: #if propensities are zero or too low, quickly end the simulation or move a bit forward
                self.t += 1/self.max_r0*0.01
                
            elif sum(self.reactant_population.values()) > 10000: #if number of reactant is to high, quickly end the simulation to avoid exploding complexity
                self.t += Tend/timepoints/2
        
    
            else:
                
                #2 ----- Generate random time step (exponential distribution)
                r1 = random.random()  
                  
                if order == 1:
                    tau = 1/a0*log(1/r1)
                    
                elif order == 2:
                    
                    
                    sum_lambda, sum_lambda_d = self.compute_propensities_second_order()
                    
                    #print(sum_lambda)
                    #print(self.reactant_population_init['A'])
                    #print(sum_lambda)
                    #print(sum_lambda2)
                    #print(sum_lambda_d)
                    
                    try:
                        tau = (-sum_lambda + sqrt(sum_lambda**2 + 2*(sum_lambda_d)*log(1/r1)))/(sum_lambda_d)
                        #print(tau)
                    except:
                        tau = Tend/timepoints/2
                        print("Warning tau out of bound")
                    #print(tau)
                    #print()
                    
                else:
                    print('Only first and second oreder are supported')
                    sys.exit()
                
                self.t += tau
                    
                    
                #3 ----- Chose the reaction mu that will occurs (depends on propensities)
                r2 = random.random()
                mu = 0
                p_sum = 0.0
                while p_sum < r2*a0:
                    p_sum += propensity[mu]
                    mu += 1
                mu = mu - 1 
                    
                
                #4 ----- Perform the reaction
                self.perform_reaction(mu,individual_rates[mu])
           
        self.population_t = interpolate_minusones(self.population_t)
        self.population_t[:,-1] = np.sum(self.population_t, axis = 1)
        


            
    def compute_propensities(self):
        """
        Compute the propensities of each reaction at current time
        """
        propensity = []
        individual_rates = []
        for reaction_chanel in self.reaction_channel_list:
            if len(reaction_chanel.reactants) > 1:
                Nreactants = np.product([self.reactant_population[reactant_str] for reactant_str in reaction_chanel.reactants])
                propensity.append(Nreactants * reaction_chanel.rate)
                individual_rates.append([]) #No individual rates for multi reactant reactions

            elif len(reaction_chanel.reactants) == 1:
                reactant_str = reaction_chanel.reactants[0]
                channel_reactant_rates = []
                for reactant_id in self.reactant_times[reactant_str][reaction_chanel.name]: #This is the computationally expensive part
                    Dt = self.t - self.reactant_times[reactant_str][reaction_chanel.name][reactant_id]
                    individual_reactant_rate, reactant_rate_derivative  = reaction_chanel.rate_function(Dt, reaction_chanel.rate, reaction_chanel.shape_param)
                    channel_reactant_rates.append(individual_reactant_rate)
                    
                individual_rates.append(channel_reactant_rates)  
                propensity.append(np.sum(channel_reactant_rates))
                
            else:
                propensity.append(reaction_chanel.rate)
                individual_rates.append([]) #No individual rates for reactions without reactants
                
        return propensity, individual_rates #individual rate is only relevant for non markovian processes
    
    
    def compute_propensities_second_order(self):
        
        lambda_ = []
        lambda_d = []
        
        for reaction_chanel in self.reaction_channel_list:
            if len(reaction_chanel.reactants) > 1:
                Nreactants = np.product([self.reactant_population[reactant_str] for reactant_str in reaction_chanel.reactants])
                lambda_.append(Nreactants * reaction_chanel.rate)
                lambda_d.append(0)

            elif len(reaction_chanel.reactants) == 1:
                reactant_str = reaction_chanel.reactants[0]
                for reactant_id in self.reactant_times[reactant_str][reaction_chanel.name]: #This is the computationally expensive part
                    Dt = self.t - self.reactant_times[reactant_str][reaction_chanel.name][reactant_id]
                    individual_reactant_rate, reactant_rate_derivative  = reaction_chanel.rate_function(Dt, reaction_chanel.rate, reaction_chanel.shape_param)

                    lambda_.append(individual_reactant_rate)
                    lambda_d.append(reactant_rate_derivative)
                
            else:
                lambda_.append(reaction_chanel.rate)
                lambda_d.append(0)
                
        sum_lambda = np.sum(lambda_) 
        sum_lambda_d = np.sum(lambda_d)

        return sum_lambda, sum_lambda_d 
    
        
        
    def perform_reaction(self,mu, individual_rates):
        """
        Perform the selected reaction mu by updating the populations of reactants and 
        products i.e. Remove reactant and add a product from their corresponding list
        
        mu: index of the reaction
        
        Note 1: 
        Some customization is necessary for this function if one want 
        to pass specific reactant properties to a product.
        
        Note 2: 
        With the current implementation, Weibull rate are supported for channels
        with only one reactant. If a chanel has more than one reactant, it is
        considered as a Poisson process
        """
        
        #Record the 
        reaction_chanel = self.reaction_channel_list[mu]
        if len(reaction_chanel.reactants) != 1: #more than 1 reactant or 0 reactants, cannot record the time before reaction
            Dt = 0
        else:
            reactant_str = reaction_chanel.reactants[0] 
            nreactants = len(individual_rates)
            probabilities = individual_rates/np.sum(individual_rates)
            index = np.random.choice(np.arange(nreactants), p=probabilities) 
            reactant = self.reactant_list[reactant_str][index]
            reactant_id = reactant.id              
            Dt = self.t - self.reactant_times[reactant_str][reaction_chanel.name][reactant_id]
            
        reaction_chanel.wait_times.append(Dt)


        #perform the reaction
        for reactant_str in reaction_chanel.reactants:
                
            if len(reaction_chanel.reactants) != 1:
                index, reactant = get_random_element(self.reactant_list[reactant_str])
                reactant_id = reactant.id
                    
                
            #Remove the reactant from reactant list and time list  
            if (reactant_str not in reaction_chanel.products) or reaction_chanel.transfer_identity == False: #dont remove the reactant if we transfert ID
                self.reactant_list[reactant_str].pop(index)
                for channel_i in self.reaction_channel_list:
                    self.reactant_times[reactant_str][channel_i.name].pop(reactant_id, None)
                #update population value
                self.reactant_population[reactant_str] -= 1
                
            
        for product_str in reaction_chanel.products:
            
            if (product_str in reaction_chanel.reactants) and reaction_chanel.transfer_identity:
                product = Reactant(ID = reactant_id) #take the reactant with the same ID as before
            else:
                product = Reactant() #make a new reactant
            product_id = product.id
                    
            #Add the reactant to reactant list and update time list
            if (product_str not in reaction_chanel.reactants) or reaction_chanel.transfer_identity == False:
                self.reactant_list[product_str].append(product)
                for channel_i in self.reaction_channel_list: #need 
                    self.reactant_times[product_str][channel_i.name][product_id] = self.t
                #update population value
                self.reactant_population[product_str] += 1

            self.reactant_times[product_str][reaction_chanel.name][product_id] = self.t
            
                
            
    def get_populations(self):
        return self.population_t
    
    def get_reactant_list(self):
        return self.reactant_list
    
    def get_channel_waiting_times(self):
        return [channel.wait_times for channel in self.reaction_channel_list]
            
            
    def plot_populations_single(self):
        timepoints = self.population_t.shape[0]
        time_points = np.linspace(0, self.Tend, timepoints)

        plt.figure(figsize = (7,4))
        plt.rcParams.update({'font.size': 16})
        for ri, reactant in enumerate(self.reactant_population.keys()):
            plt.plot(time_points, self.population_t[:,ri], 'k-', lw=2, alpha=1,color=sns.color_palette()[ri], label=reactant)
        plt.xlabel('Time [%s]' % self.param.unit)
        plt.ylabel('Population')
        plt.legend()
        plt.show()
        
    def plot_populations(self, reactant_list = None, log_scale = False, color_list = [], figsize = (6,4)):
        
        
        reactant_poplist = list(self.reactant_population_init.keys())
        reactant_poplist.append('Total')
        
        if reactant_list is None:
            reactant_list = reactant_poplist
            
        if len(color_list) < len(reactant_list):
            c_init = len(color_list)
            for i in range(len(color_list),len(reactant_list)):
                color_list.append(sns.color_palette()[i + 1 - c_init])
        
        population = self.population_compiled
        """ploting the population"""
        N_simulations = population.shape[0]
        N_reactants = population.shape[2]
        timepoints = population.shape[1]
        time_points = np.linspace(0, self.Tend, timepoints)
        lwm = 3
        plt.figure(figsize = figsize)
        plt.rcParams.update({'font.size': 16})
        rii = 0
        for ri in range(N_reactants):
            if reactant_poplist[ri] in reactant_list:
                for i in range(N_simulations):
                    plt.plot(time_points, population[i,:,ri], 'k-', lw=0.3, alpha=0.1,color=sns.color_palette()[0])
                plt.plot(time_points, population[:,:,ri].mean(axis=0), 'r-', lw=lwm, color=color_list[rii], label=reactant_poplist[ri])
                rii += 1
            plt.xlabel('Time [%s]' % self.param.unit)
        plt.ylabel('Population')
        plt.legend()
        if log_scale: plt.yscale('log')
        plt.show()
        
        
    def plot_inter_event_time_distribution(self, color_list = None):
        
        
        for ri,reaction_chanel in enumerate(self.reaction_channel_list):
            wait_times = np.array(reaction_chanel.wait_times)
            
            print("\n Reaction chanel %s:" % reaction_chanel.name)

            if len(wait_times) == 0:
                print('   This reaction has never occured')
            else:
                if len(reaction_chanel.reactants) != 1:
                    print('   This channel reacted %.2f times per simulation on average.' % (len(wait_times)/self.param.N_simulations))
                    print('   No distribution can be plotted as the definition of time')
                    print('   before reaction for non unique reactant is ambigious.')
                else:
                
                    if color_list is None:
                        colori = sns.color_palette()[(ri+4) % 10]
                    else:
                        colori = color_list[ri]
                    #bins = np.linspace(0,30,30)
                    bins = 30
                    plt.hist(wait_times, bins = bins, color = colori, density=True, edgecolor='black')
                    plt.xlabel("Time before reaction [%s]" % self.param.unit)
                    plt.ylabel("PDF")
                    plt.title(reaction_chanel.name)
                    t = np.linspace(np.max(wait_times)/100000, np.max(wait_times), 10000)                 
                        
                    shape_param = reaction_chanel.shape_param
                    rate = reaction_chanel.rate
                    distribution = reaction_chanel.distribution
                    if distribution.lower() in ['exponential', 'exp']:
                        pdf_true = rate*np.exp(-rate*t)
                        P = stat.expon.fit(wait_times,floc=0)
                        pdf = stat.expon.pdf(t, *P)
                            
                    elif distribution.lower() in ['weibull','weib']:
                        alpha = shape_param
                        beta = (alpha) * (rate * gamma((alpha + 1)/(alpha)))**(alpha)
                        pdf_true = beta*np.power(t,alpha-1)*np.exp(-beta*np.power(t,alpha)/(alpha))
                        if reaction_chanel.shape_param == 1:
                            P = stat.expon.fit(wait_times,floc=0)
                            pdf = stat.expon.pdf(t, *P)
                        else:
                            P = stat.weibull_min.fit(wait_times,3, floc=0, scale = 30)
                            pdf = stat.weibull_min.pdf(t, *P)
                            
                    elif distribution.lower() in ['gaussian', 'normal', 'norm']:
                        mu = 1/rate
                        sigma = mu*shape_param
                        pdf_true = 1/(sigma*sqrt(2*pi)) * np.exp(-(1/2) * np.power((t-mu)/sigma,2))
                        P = stat.norm.fit(wait_times)
                        pdf = stat.norm.pdf(t, *P)
                        
                    elif distribution.lower() in ['gamma','gam']:
                        alpha = shape_param
                        beta = alpha*rate
                        pdf_true = (beta**alpha)*np.power(t,alpha-1)*np.exp(-beta*t)/gamma(alpha)
                        P = stat.gamma.fit(wait_times,floc=0)
                        pdf = stat.gamma.pdf(t, *P)
                        
                    elif distribution.lower() in ['lognormal','lognorm']:
                        mu0 = 1/rate
                        sigma0 = mu0*shape_param
                        mu = log(mu0**2 / sqrt(mu0**2 + sigma0**2))
                        sigma = sqrt(log(1+ sigma0**2/mu0**2))
                        pdf_true = 1/(t*sigma*sqrt(2*pi)) * np.exp(-(1/2) * np.power((np.log(t)-mu)/sigma,2))
                        P = stat.lognorm.fit(wait_times,floc=0)
                        pdf = stat.lognorm.pdf(t, *P)
                        
                    elif distribution.lower() in ['cauchy', 'cau']:
                        gam = shape_param
                        mu = 1/rate
                        pdf_true = 1 / (pi*gam*(1 + ((t-mu)/gam)**2))
                        P = stat.cauchy.fit(wait_times)
                        pdf = stat.cauchy.pdf(t, *P)
                        
                    plt.plot(t, pdf, 'r',lw=2, label = 'Fitted')   
                    plt.plot(t, pdf_true, 'green',lw=2, linestyle = '--', label = 'Theory') 
                    plt.legend()
                    plt.xlim(0,max(wait_times)*1.1) 
                    plt.show()
                    
                    print("   Obtained rate is %.3f vs %.3f" % (1/np.mean(wait_times),reaction_chanel.rate))
                    print("   Corresponding to %.1fh vs %.1fh" % (np.mean(wait_times),1/reaction_chanel.rate))
                    if reaction_chanel.shape_param != 0:
                        print("   Fitted params [%.2f,%.2f] vs shape_param %.2f" % (P[0],P[1],reaction_chanel.shape_param))
                    print("   std is %.1fh" % (np.std(wait_times)))
                    
                    
        print()
        print('  - It is possible that the distribution do not match for reactions')
        print('    where the same reactant is involved in more than one reaction,')
        print('    or if at least one product of the reaction is a reactant.')
        print()
        print('  - Aslo, if not in the steady state, a continiously increasing population') 
        print('    will bias the time to event distribution to lower average time by')
        print('    continiously generating new reactants with Dt = 0')
        print()
        print('  - Other reasons include a too small simulation time (Tend)') 
        print('    or not enough repetition of the Gillepie simulations.')

            
            
            
def get_random_element(a_huge_key_list):
    L = len(a_huge_key_list)
    i = np.random.randint(0, L)
    return i, a_huge_key_list[i]            

def interpolate_minusones(y):
    """
    Replace -1 in the array by the interpolation between their neighbor non zeros points
    y is a [t] x [n] array 
    """
    x = np.arange(y.shape[0])
    ynew = np.zeros(y.shape)
    for ni in range(y.shape[1]):
        idx = np.where(y[:,ni] != -1)[0]
        if len(idx)>1:
            last_value = y[idx[-1],ni]
            interp = interp1d(x[idx],y[idx,ni], kind='previous',fill_value=(0,last_value),bounds_error = False) 
            ynew[:,ni] = interp(x)
            
        elif len(idx) == 1:
            last_value = y[idx[-1],ni]
            ynew[:,ni] = last_value
    return ynew
        
        
        
if __name__ == "__main__":
    plt.rcParams.update({'font.size': 16})
    #test = __import__('__TEST_REGIR_multiple_reactants')
    test = __import__('Benchmarking_accuracy')
    import random as rd
    test.main()        
        
