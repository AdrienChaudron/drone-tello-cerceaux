%SELCSTRUC allows to select the best model structures for SRIVC or TFSRIVC
%   according to various criteria.
%
%   Syntax :
%
%      [NN,Vcrit] = selcstruc(V,Algo)
%      [NN,Vcrit] = selcstruc(______,'Name',Value)
%
%   NN    : contains the structures of the 'Nmodels' best estimated
%           models, sorted by the criterion 'c2sort'. Each row contains a
%           different model structure.
%   Vcrit : contains the criteria associated with the model structures NN
%           from above. The first row is the number given to the models.
%           Then, each row contains the following criteria :
%           - SRIVCSTRUC case : [YIC RT2e RT2v FPE AIC log(cond(P)) Niter]
%             (RT2e and RT2v are RT2 considering estimation data and
%             validation data, respectively).
%           - TFSRIVCSTRUC case : [FITe FITv Niter].
%
%   V     : is a matrix containing information about different structures
%           obtained as the output of SRIVCSTRUC or TFSRIVCSTRUC.
%   Algo  : SELCSTRUC can be used with the output matrix V from SRIVCSTRUC
%           or TFSRIVCSTRUC. Use 'srivcstruc' as a value of 'Algo' in the
%           first case and 'tfsrivcstruc' in the second.
%
%   Additional estimation options can be specified through name-value
%   pair arguments :
%
%   'Nmodels' : is the number of estimated models to be displayed for
%               comparison (5 by default). Write 'all' to display all
%               the available combinations for the given value of NN.
%   'c2sort'  : is a sorting criterion, i.e., the results are sorted
%               according to the value specified in 'c2sort'.
%               'Niter' and 'Nparam' are options available in both cases.
%               (Niter : number of iteration, Nparam : number of parameters).
%               Specific options :
%               - SRIVCSTRUC case : 'YIC' (by default), 'RT2e', 'RT2v',
%                 'FPE','AIC' or 'COND'.
%               - TFSRIVCSTRUC case : 'FITe' (by default) or 'FITv'.
%   'c'       : is additional criteria to display in the figure.
%               'Niter' is an option available in both cases.
%               Specific options :
%               - SRIVCSTRUC case : by default 'YIC' and 'RT2e' are
%                 displayed. Thus, the values for 'c' can be 'RT2v',
%                 'FPE', 'AIC' and/or 'COND'.
%                 Examples : 'c','FPE'
%                            'c',{'RT2v','Niter','AIC'}
%               - TFSRIVCSTRUC case : by default 'FITe' is displayed. The
%                 value for 'c' can be 'FITv'.
%                 Examples : 'c','YIC'
%                            'c',{'Niter','FITv'}
%   'Display'  : It can be either 'console' or 'graph' (by default). Results
%                with advices will be printed in a figure or in the console.
%                It is possible to see few lines of important information
%                in the console with 'graph' as a value. Use 'graphonly' as
%                a value if they are truly not necessary.
%                Remark : nothing at will be displayed if at least
%                         one output argument has been entered.
%
%   The user can also impose some bounds on the results displayed by SELCSTRUC :
%   - SRIVCSTRUC case :
%     'YICb'   : upper bound for YIC (+Inf by default)
%     'RT2eb'  : lower bound (0 by default) for RT2 considering estimation data
%     'RT2vb'  : lower bound (0 by default) for RT2 considering validation data
%     'FPEb'   : upper bound for FPE (+Inf by default)
%     'AICb'   : upper bound for AIC (+Inf by default)
%     'CONDb'  : upper bound for COND (+Inf by default)
%     'Niterb' : upper bound for Niter (10 by default)
%   - TFSRIVCSTRUC case :
%     'FITeb'  : lower bound for FIT considering estimation data (0 by default)
%     'FITvb'  : lower bound for FIT considering validation data (0 by default)
%     'Niterb' : upper bound for Niter (50 by default)
%
%	authors  : Hugues Garnier - Eric Huselstein
%	date     : 07 Nov. 2001
%	revision : 18 Nov. 2001
%              10 Oct. 2003 by H.Garnier
%              17 May  2005 by H.Garnier
%              03 Feb. 2016 by A.Padilla
%              04 May  2020 by H.Muller (added the TFSRIVCSTRUC case)
%   name     : selcstruc.m
%
%	CRAN - Centre de Recherche en Automatique de Nancy
%	e-mail : hugues.garnier@univ-lorraine.fr


