%	TFSRIVC estimates the parameters of continuous-time output-error models
%   with time-delay using the SRIVC (Simple Refined Instrumental Variable
%   for Continuous-time models) method.
%
%   Syntax:
%
%      sys = TFSRIVC(data, np, nz)
%      sys = TFSRIVC(data, np, nz, IODelay)
%      sys = TFSRIVC(___, Name, Value)
%
%   sys      : Returned IDTF model.
%
%   data     : Data in IDDATA object format.
%              Data are either equally or nonequally sampled.
%   np       : Number of poles in the denominator.
%   nz       : Number of zeros in the numerator.
%   IODelay  : Initial time delay.
%
%   Additional estimation options can be specified through name-value pair
%   arguments. The following names are considered:
%       a. 'TdMin'        : Lower time-delay boundary.
%                         	  Default: 0.
%       b. 'TdMax'        : Upper time-delay boundary.
%                             Default: calculated by maximizing the cross
%                             correlation of the input-output data.
%       c. 'TolPar'       : Tolerence of parameter changes.
%                             Default: 1e-4.
%       d. 'TolFun'       : Tolerence of loss function changes.
%                             Default: 1e-4.
%       e. 'StepMax'      : Maximum time-delay increment.
%                             Default: inf.
%       f. 'StepReduction': Time-delay increment reduction factor (should
%                           be larger than 1).
%                             Default: 2
%       g. 'MaxIter'      : Maximum iteration number.
%                             Default: 100.
%       h. 'FixTd'        : Fixing the time delay. Then, the plant model
%                           parameters are estimated by fixing the time
%                           delay
%                             Default: 'off', can be switched to 'on'.
%       i. 'Integration'  : Integration enforced for the estimation of
%                           models (not applicable if a focus filter is
%                           enabled).
%                             Default: 'off', can be switched to 'on'.
%       j. 'Focus'        : Cutoff frequency of the focus filter (in
%                           rad/time unit, implemented as a Butterworth
%                           filter) used for prefiltering the data.
%                             Default: inf (all pass).
%       k. 'FocusOrder'   : Order of the Focus filter.
%                             Default: 5.
%       l. 'NumTd'        : Number of time-delay values in [TdMin TdMax] to
%                           be compared if IODelay is not provided.
%                             Default: 5.
%       m. 'Lambda'       : Cutoff frequency of the state variable filter
%                           (in rad/time unit).
%                             Default: 1/50 the Nyquist frequency
%
%   If 'IODelay' is not specified, the exhaustive search technique in Chen
%   et al (2018) will be used to generate a reliable initial time delay.
%
%   An alternative syntax is:
%
%      model = TFSRIVC(data, Mi, Name, Value)
%
%   Mi is an estimated model or a model created by IDTF containing
%   structure information and initial values for the parameters. Note that
%   we only extract three parameters from Mi: IODelay, Den and Num. Other
%   parameters, e.g., TdMin and TdMax, should be set through name-value
%   pairs.
%
%   See for further explanations:
%
%   Chen, F., Zhuan, X., Garnier, H., Gilson, M., "Issues in separable
%   identification of continuous-time models with time-delay", Automatica,
%   94, 258-273, 2018.


