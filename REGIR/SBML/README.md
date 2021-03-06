# Interacting with SBML files

The Systems Biology Markup Language (SBML) is a format based on `.xml` and a standard for representing computational models in systems biology. REGIR can read and write models in the SBML format, but first you need to install the `libSBML` and `simplesbml` libraries with:

	- pip install libSBML
	- pip install simplesbml
	

### Saving REGIR model as SBML
You can store any of your models built with REGIR with the `get_model_in_SBML()` method. Note that in REGIR, the rate laws are always proportional to the number of reactants. For example, the reaction (A+B -> C) will have a propensity of *a = A x B x r*. Because the SBML format is originally designed only for Markovian processes, the additional parameters related the non-markovian processes such as the shape parameter or the type of distribution are stored in the `local_params` field of the reaction definition of `libSBML` (see source code for details about the implementation).

    import REGIR as gil
    #Define params, N_init and reaction_channel_list
    ...
    
    #Create the REGIR model
    G_simul = gil.Gillespie_simulation(N_init,params)
    G_simul.reaction_channel_list = reaction_channel_list
    
    #Save the SBML file
    sbml_model = G_simul.get_model_in_SBML()
    with open("model.sbml", "w") as text_file:
        text_file.write(sbml_model.toSBML())

 
### Loading an SBML model into REGIR
You can read SBML models with the `build_model_from_SBML` function provided in the `REGIR_SBML.py` file:

    class simulation_param:
	    Tend = 200		#Length of the simulation
	    N_simulations = 20	
	    unit = 'h'		#Unit of time (used for plotting only)
	    timepoints = 100	#Number of timepoints to record (used for plotting only)
    
    #Load SBML file
    SBML_file = 'your_model.sbml'
    from REGIR_SBML import REGIR_from_SBML
    REGIR_SBML = REGIR_from_SBML(verbose=True)
    G_simul = REGIR_SBML.build_model_from_SBML(SBML_file, simulation_param)
  
    #Run the simulation
    G_simul.run_simulations(param.Tend, verbose = False)
    G_simul.plot_inter_event_time_distribution()
    G_simul.plot_populations()
 
The function is maily useful to load SBML files generated by REGIR. While many SBML models are available in the BioModels database (https://www.ebi.ac.uk/biomodels/), the majority of them are unfortunatly not compatible with REGIR. In fact, REGIR currently only supports rate laws that are proportional to reactant amounts and that do not depend on other populations. Also, As REGIR creates an explicit list of reactants to store their individual properties, dealing with concentrations rather than reactant amount makes the definition of the model ambigious. Still, many of the models on the BioModels database can be adapated to the REGIR framework with some manual adjustement. 

*Feel free to email me if you have a specific SBML model in mind for which you would like to test non-exponential distributions.*
