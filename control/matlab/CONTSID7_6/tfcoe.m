%   TFCOE  Computes the parameters of continuous-time output-error models
%   with time-delay using the COE method.
%
%   Syntax:
%
%      sys = TFCOE(data,np,nz)
%      sys = TFCOE(data,np,nz,IODelay,'Name',Value)
%      sys = TFCOE(___,Name,Value)
%
%   sys      : Returned IDTF model.
%   data     : Data in IDDATA object format, see help IDDATA.
%              Data are either equally or nonequally sampled.
%   nz       : Number of zeros in the numerator.
%   np       : Number of poles in the denominator.
%   IODelay  : Initial time-delay.
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
%                             (should be larger than 1)
%                               Default: 2
%       g. 'MaxIter'        : Maximum iteration number.
%                               Default: 100
%       h. 'Integration'    : Indicator of integration enforced for the
%                             estimation of models (not applicable if the
%                             focus filter is enabled).
%                               Default: 'off', can be switched to 'on'
%       i. 'OverPar'        : Indicator for over-parametrization. The
%                             denominator degree becomes nf + 1 at the
%                             initialization stage. Overparametrization is
%                             not suggested to be used with Integration.
%                               Default: 'off', can be swithched to 'on'
%       j. 'Focus'          : Cutoff frequency of the focus filter (in
%                             rad/time unit, implemented as a Butterworth
%                             filter) used for prefiltering the data.
%                               Default: inf (all pass filter)
%       k. 'FocusOrder'     : Order of the Focus filter.
%                               Default: 5
%       l. 'NumTd'          : Number of time-delay values in [TdMin TdMax]
%                             to be compared if IODelay is not provided.
%                               Default: 50
%       m. 'Lambda'         : Cutoff frequency the state variable filter
%                             (in rad/time unit).
%                               Default: 1/50 the Nyquist frequency.
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
%      model = TFCOE(data,Mi,Name,Value)
%
%   Mi is an estimated model or a model created by IDTF containing
%   structure information and initial values for the parameters. Note that
%   we only extract three parameters from Mi: IODelay, Den and Num. Other
%   parameters, e.g., TdMin and TdMax, should be set through name-value
%   pairs.
%
%   See for further explanations:
%
%   Chen, F., Gilson, M., Garnier, H., Liu, T., "Robust time-domain output
%   error method for identifying continuous-time systems with time delay",
%   Systems & Control Letters, 102:81-92, 2017.


