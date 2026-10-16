%	TFRIVC estimates the parameters of a single-input single-output or
%	multi-input single-output continuous-time hybrid Box-Jenkins models
%	with multiple time delays using the RIVC (Refined Instrumental Variable
%	for Continuous-time models) method. The plant is modeled in the
%	continuous-time domain while the noise is modeled in the discrete-time
%	domain.
%
%   Syntax:
%
%      [MP, MN] = TFRIVC(data, np, nz)
%      [MP, MN] = TFRIVC(data, np, nz, iodelay)
%      [MP, MN] = TFRIVC(___, Name, Value)
%
%   MP       : Returned IDTF model for the plant.
%   MN       : Returned IDPOLY model for the noise.
%
%   data     : Data in IDDATA object format.
%   np       : Number of poles in the denominator, [np1, np2, ... ].
%   nz       : Number of zeros in the numerator, [nz1, nz2, ... ].
%   iodelay  : Initial time delays, [iodelay1, iodelay2, ... ].
%
%   Additional estimation options can be specified through name-value pair
%   arguments. The following names are considered:
%       a. 'TdMin'        : Lower time-delay boundary, [TdMin1, TdMin2, ...].
%                           TdMin1 stands for the lower time-delay boundary
%                           for channel 1.
%                         	  Default: [0, ..., 0].
%       b. 'TdMax'        : Upper time-delay boundary, [TdMax1, TdMax2, ...].
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
%       j. 'NN'           : Noise transfer function degrees [nd, nc], where
%                           nd denotes the denominator degree while nc the
%                           numerator degree. The noise is estimated as a
%                           DT ARMA model (requring the MATLAB SID
%                           toolbox). Data should be equally sampled if the
%                           NN function is enabled.
%                             Default: [], no noise model is assumed.
%       k. 'Focus'        : Cutoff frequency of the focus filter (in
%                           rad/time unit, implemented as a Butterworth
%                           filter) used for prefiltering the data.
%                             Default: inf (all pass).
%       l. 'FocusOrder'   : Order of the Focus filter.
%                             Default: 5.
%       m. 'NumTd'        : Number of time-delay values in [TdMin TdMax] to
%                           be compared if iodelay is not provided,
%                           [NumTd1, NumTd2, ...].
%                             Default: [20, 20, ...].
%       n. 'Lambda'       : Cutoff frequency of the state variable filter
%                           (in rad/time unit).
%                             Default: 1/50 the Nyquist frequency
%
%   If iodelay is not specified, the exhaustive search technique similar to
%   that in Chen et al (2018) will be used to generate a reliable initial
%   time delay.
%
%   An alternative syntax is:
%
%      [MP, MN] = TFRIVC(data, Mi, Name, Value)
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
%
%   Chen, F., Young, P.C., Garnier, H., Deng, Q., Kazimierczuk, M.K.,
%   "Data-driven modeling of wireless power transfer systems with multiple
%   transmitters", IEEE Transactions on Power Electronics", 35(11),
%   11363-11379, 2020.


