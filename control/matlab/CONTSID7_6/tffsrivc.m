%   TFFSRIVC estimates the parameters of continuous-time output error
%   models with time-delay using the frequency domain SRIVC (Simple Refined
%   Instrumental Variable for Continuous-time models) method.
%
%   Syntax:
%
%      sys = TFFSRIVC(data,np,nz)
%      sys = TFFSRIVC(data,np,nz,IODelay)
%      sys = TFFSRIVC(___,Name,Value)
%
%   sys         : Returned IDTF model.
%   data        : Time-domain data in IDDATA object format, see help
%                 IDDATA. Data should be equally sampled.
%   nz          : Number of zeros in the numerator.
%   np          : Number of poles in the denominator.
%   IODelay     : Initial time-delay.
%
%   Additional estimation options can be specified through name-value pair
%   arguments. The following names are considered:
%       a. 'TdMin'          : Lower time-delay boundary.
%                               Default: 0
%       b. 'TdMax'          : Upper time-delay boundary.
%                               Default: calculated by maximizing the cross
%                               correlation function of the input-output
%                               data
%       c. 'TolPar'         : Tolerence of parameter changes.
%                               Default: 1e-4
%       d. 'TolFun'         : Tolerence of loss function changes.
%                               Default: 1e-4
%       e. 'StepMax'        : Maximum time-delay increment.
%                               Default: inf
%       f. 'StepReduction'  : Time-delay increment reduction factor
%                             (should be larger than 1).
%                               Default: 2
%       g. 'MaxIter'        : Maximum iteration number.
%                               Default: 100
%       h. 'FixTd'          : Fixing the time-delay or not.
%                               Default: 'off', can be switched to 'on'
%       i. 'IntSamp'        : Indicator for integrated sampling.
%                               Default: 'on', it can be switched to 'off'
%       j. 'NumTd'          : Number of time-delay values in [TdMin TdMax]
%                             to be compared if IODelay is not provided.
%                               Default: 50
%       k. 'Lambda'         : Cutoff frequency the state variable filter
%                             (in rad/time unit).
%                               Default: 1/50 the Nyquist frequency
%
%   If 'IODelay' is not specified, the exhaustive search technique in Chen
%   et al (2018) will be used to generate a reliable initial time-delay.
%
%   Chen, F., Zhuan, X., Garnier, H., Gilson, M., "Issuess in separable
%   identification of continuous-time models with time-delay", Automatica,
%   2018.
%
%   An alternative syntax is:
%
%      model = TFFSRIVC(data,Mi,Name,Value)
%
%   Mi is an estimated model or a model created by IDTF containing
%   structure information and initial values for the parameters. Note that
%   we only extract three parameters from Mi: IODelay, Den and Num. Other
%   parameters, e.g., TdMin and TdMax, should be set through name-value
%   pairs.


