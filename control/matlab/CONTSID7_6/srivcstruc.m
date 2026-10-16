%SRIVCSTRUC Computes the YIC fit and the coefficient of determination
%   for families of MISO continuous models (with different or common
%   denominators) estimated by SRIVC.
%
%   Syntax :
%
%      V = srivcstruc(Ze,[],NN)
%      V = srivcstruc(Ze,Zv,NN)
%      V = srivcstruc(________,'Name',Value)
%
%   V: [NN YIC RT2e RT2v FPE AIC log(cond(P)) Niter n0e n0v]
%   NN is the first output argument. It is composed of nb, nf and nk for
%   each inputs (then, its number of columns is equal to the number of
%   inputs times 3). All of the following parameters are only one column
%   wide and are computed for models of the structures defined by the rows
%   of NN (these models being estimated by the SRIVC method). Accordingly,
%   the second output arg is returned as the Young's Information Criterion.
%   In the same way, the third and the fourth parameters, RT2e and RT2v
%   (computed on the estimation set Ze and the validation set Zv,
%   respectively), are the coefficients of determination based on the
%   simulation error. The seventh output arg contains the logarithms of the
%   IV-matrix conditioning numbers. Niter is simply the number of iteration
%   that the algorithm took to converge to a solution for a particular set
%   of parameters in NN. As for the last 2 columns, they contain the number
%   of data points used for estimation/validation.
%   Note : a line with NN followed by only 0 and Inf values means that the
%          estimation of the model for this particular line has failed.
%
%   Ze : The estimation data in IDDATA object format.
%   Zv : The validation data on which the cross-validation is performed
%        in IDDATA object format (equal Ze by default).
%   NN : is of the format [nb_min nf_min nk_min; nb_max nf_max nk_max], where
%        nb_min(max) : smallest(highest) parameter numbers for the numerator
%        nf_min(max) : smallest(highest) parameter numbers for the denominator
%        nk_min(max) : smallest(highest) integer number of sampling period for
%                       the delay (zero for nonequally sampled data)
%        For the MISO case, NN is the horizontal concatenation of NNs.
%        Exemple with 3 inputs : NN = [NN1 NN2 NN3] (NN1 is the NN parameter
%                                associated to the transfer function
%                                of the first input, and so on).
%
%   By default the SRIVC method is initiated from the discrete-time version
%   SRIV of the SRIVC method. The discrete-time model is converted into
%   continuous-time. This initialisation approach does not require to
%   specify lambda.
%
%   Additional estimation options can be specified through name-value
%   pair arguments :
%
%   'lambda'      : is the cut-off frequency of the Poisson filter chain
%                   element for the initial parameter estimation if the
%                   choice is to initiate the SRIVC method by using the
%                   IV-based GPMF estimation method (lambda should be a
%                   strictly positive number and it should be chosen close
%                   to the system bandwidth).
%                   For the MISO case, lambda is the horizontal concatenation
%                   of lambdas. Exemple with 3 inputs : 'lambda',[lb1 1b2 lb3]
%                   (lb1 is the lambda parameter associated to the transfer
%                   function of the first input, and so on).
%   'n0e'         : is the starting estimation index for estimation.
%                   By default, n0e is set to 1.
%   'n0v'         : is the starting estimation index for cross-validation. By
%                   default, n0v is set to 1. The coefficient of determination
%                   for cross validation, RT2v, is calculated from n0v.
%   'Denominator' : For MISO transfer functions the denominators can be
%                   'Different' or 'Common'. The default value is 'Different'.
%   'fig'         : is a uifigure. It allows the user to integrate the progress
%                   bar into a figure instead of having the default waitbar
%                   floating around. A figure handle is required in order to
%                   use that argument, as the following : 'fig',figureHandle
%
%	authors  : Eric Huselstein - Hugues Garnier
%	date     : 23 Oct. 2001
%	revision : 08 Nov. 2001
%                 Jun. 2003 for version 3.0 of the CONTSID toolbox
%                           Modified by HG 10 Oct 2003 and 18 Apr 2005
%              04 May  2020 by H.Muller
%   name     : srivcstruc.m
%
%	CRAN - Centre de Recherche en Automatique de Nancy
%	e-mail : hugues.garnier@cran.uhp-nancy.fr


