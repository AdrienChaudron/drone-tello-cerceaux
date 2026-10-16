%   TFSRIVC_INIT computes an initial model for the identification of
%   continuous-time output-error models with time-delay using the TFSRIVC
%   method.
%
%   Syntax:
%
%      sys = TFSRIVC_INIT(data,np,nz)
%      sys = TFSRIVC_INIT(___,Name,Value)
%
%   sys      : Returned IDTF model.
%   data     : Data in IDDATA object format, see help IDDATA.
%              Data are either equally or nonequally sampled.
%   nz       : Number of zeros in the numerator.
%   np       : Number of poles in the denominator.
%
%   Additional estimation options can be specified through name-value pair
%   arguments. The following names are considered:
%       a. 'TdMin'      : Lower time-delay boundary.
%                           Default: 0
%       b. 'TdMax'      : Upper time-delay boundary.
%                           Default: calculated by maximizing the cross
%                           correlation function of the input-output data
%       c. 'Lambda'     : Cutoff frequency the state variable filter (in
%                         rad/time unit).
%                           Default: 1/50 the Nyquist frequency.
%       d. 'NumTd'      : Number of time-delay values in [TdMin TdMax] to
%                         be compared if IODelay is not provided.
%                           Default: 50
%
%   See for further explanations :
%
%   Chen, F., Zhuan, X., Garnier, H., Gilson, M., "Issuess in separable
%   identification of continuous-time models with time-delay", Automatica,
%   2018.


