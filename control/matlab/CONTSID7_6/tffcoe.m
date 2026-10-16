%   TFFCOE  Computes the parameters of continuous-time output-error models
%   with time-delay using the frequency-domain COE method.
%
%   Syntax:
%
%      sys = TFFCOE(data,np,nz)
%      sys = TFFCOE(data,np,nz,IODelay)
%      sys = TFFCOE(___,Name,Value)
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
%                               Default: Calculated by maximizing the cross
%                               correlation function of the input-output
%                               data
%       c. 'TolPar'         : Tolerence of the parameter changes.
%                               Default: 1e-4
%       d. 'TolFun'         : Tolerence of the loss function value changes.
%                               Default: 1e-4
%       e. 'StepMax'        : Maximum time-delay increment.
%                               Default: inf
%       f. 'StepReduction'  : Parameter increment reduction factor.
%                             (should be larger than 1).
%                               Default: 2
%       g. 'MaxIter'        : Maximum iteration number.
%                               Default: 100
%       h. 'IntSamp'        : Indicator for integrated sampling.
%                               Default: 'on', it can be switched to 'off'
%       i. 'NumTd'          : Number of time-delay values in [TdMin TdMax]
%                             to be compared if IODelay is not provided.
%                               Default: 50
%       j. 'Lambda'         : Cutoff frequency the state variable filter
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
%      model = TFFCOE(data,Mi,Name,Value)
%
%   Mi is an estimated model or a model created by IDTF containing
%   structure information and initial values for the parameters. Note that
%   we only extract three parameters from Mi: IODelay, Den and Num. Other
%   parameters, e.g., TdMin and TdMax, should be set through name-value
%   pairs.
%
%   See for further explanations :
%
%   Chen, F., Garnier, H., Gilson, M., X. Zhuan, "Frequency domain
%   identification of continuous-time output-error models with time-delay
%   from relay feedback tests",
%   Submitted to a journal, 2018.


