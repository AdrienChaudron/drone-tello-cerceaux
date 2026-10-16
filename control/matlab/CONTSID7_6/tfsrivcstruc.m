%TFSRIVCSTRUC Computes the FIT, as the percentage of sameness between the
%   model output (YS) and the output of the data (Y), for families of
%   MISO continuous models estimated by TFSRIVC. The fit is calculated as:
%       FIT = 100 * (1-norm(Y-YS)/norm(Y-mean(Y))) (in %)
%
%   Syntax :
%
%      V = tfsrivcstruc(Ze,[],NN)
%      V = tfsrivcstruc(Ze,Zv,NN)
%      V = tfsrivcstruc(________,'Name',Value)
%
%   V: [FITe FITv Niter]
%   The first column of V is returned as the FITe percentage (see formula
%   above) and is computed on the estimation set Ze. The next column, FITv
%   is the same as FITe but computed on the validation set Zv. The last
%   column of V contains the number of iteration that the algorithm took
%   to converge to a solution for a particular set of parameters in NN.
%   Note : a line with NN followed by only 0 and Inf values means that the
%          estimation of the model for this particular line has failed.
%
%   Ze : The estimation data in IDDATA object format.
%   Zv : The validation data on which the cross-validation is performed
%        in IDDATA object format (equal Ze by default).
%   NN : is of the format [nz_min np_min; nz_max np_max], where
%        nz_min(max) : smallest(highest) parameter numbers for the numerator
%        np_min(max) : smallest(highest) parameter numbers for the denominator
%        For the MISO case, NN is the horizontal concatenation of NNs.
%        Exemple with 3 inputs : NN = [NN1 NN2 NN3] (NN1 is the NN parameter
%                                associated to the transfer function
%                                of the first input, and so on).
%
%   An additional estimation option can be specified through name-value
%   pair arguments :
%
%   'Td'  : is the time delay. It can be either 'auto' or a positive
%           numerical value, 'auto' being the default value. For the
%           MISO case, it is a cell vector with as my colums as inputs.
%           Exemple with 3 inputs : 'Td',{5,'auto',0} (5 is the delay
%                                   associated to the transfer function
%                                   of the first input, and so on).
%   'fig' : is a uifigure. It allows the user to integrate the progress
%           bar into a figure instead of having the default waitbar
%           floating around. A figure handle is required in order to
%           use that argument, as the following : 'fig',figureHandle
%
%	authors  : Hugo Muller
%	date     : 04 May 2020
%	revision : /
%   name     : tfsrivcstruc.m
%
%	CRAN - Centre de Recherche en Automatique de Nancy
%	e-mail : hugues.garnier@cran.uhp-nancy.fr


