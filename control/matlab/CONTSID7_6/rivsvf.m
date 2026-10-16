%RIVSVF  Estimates recursively in real time the parameters of a LTI or LTV
%   system using the IVSVF method.
%
%   Syntax :
%
%      [THM,YH,PSET] = RIVSVF(data,nn,'lambda_svf',lambda_svf)
%      [THM,YH,PSET] = RIVSVF(data,nn,'lambda_svf',lambda_svf,'Name',Value)
%
%   THM    : matrix containing the estimated parameters. Row k contains the
%            estimates "in alphabetic order" corresponding to time k.
%   YH     : estimated output.
%   PSET   : set of parameter covariance matrices for every recursion k.
%   data   : The estimation data in IDDATA object format.
%            Data are either equally or nonequally sampled.
%            For more information type "help IDDATA"
%   nn = [na nb nk] where
%      na  : number of parameters to be estimated for the denominator
%      nb  : number of parameters to be estimated for the numerator
%      nk  : delay of the model (integer number of sampling period Ts)
%            (nk=0 for nonequally sampled data)
%   lambda_svf : cut-off frequency (rad/s) of the State Variable Filter
%
%   Additional estimation options can be specified using name-value
%   pair arguments.
%
%   The recursive estimation algorithm is specified defining two name-value
%   pairs. The default option is: 'adm','ff','adg',1.
%   'adm' : adaptation mechanism. The possible values for 'adm' are:
%           'ff' : forgeting factor algorithm
%           'kf' : Kalman filter based algorithm
%   'adg' : adaptation gain. The possible values for 'adg' depend on the
%           algorithm. For ...
%           'ff' : 'adg' is the value of the forgetting factor, i.e. a
%                  scalar in the interval [0,1].
%           'kf' : 'adg' is the normalized covariance matrix of the Kalman
%                  filter.
%   'tsiv' : time instant at which RIVSVF starts to operate.
%           RIVSVF is initialized with RLSSVF, and tsiv should be chosen
%           based on the convergence of RLSSVF. The convergence of RLSSVF
%           can be checked by running this algorithm and comparing
%           the measured output y with the estimated output yh. yh is the
%           second output argument of the estimation routines.
%           Default: tsiv = ttotal/10, with ttotal the total simulation
%           time.
%   'dtupdate' : period of time at which the auxiliary model is updated.
%   'th0' : Initial value for the parameters
%   'P0'  : Initial value of "P-matrix"
%
%   Reference :
%   A. Padilla, H. Garnier, P.C. Young, J. Yuz. "Real-time identification
%   of linear continuous-time systems with slowly time-varying parameters",
%   IEEE Control and Decision Conference, Las Vegas USA, 2016.


