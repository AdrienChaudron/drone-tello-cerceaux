%   TFRSRIVC_SEP estimates recursively the parameters of a continuous-time
%   LTI transfer function model with time delay using the recursive SRIVC
%   method.
%
%   Syntax:
%
%      [thm, ev, Ps] = tfrsrivc_sep(data, np, nz)
%      [thm, ev, Ps] = tfrsrivc_sep(data, np, nz, iodelay)
%      [thm, ev, Ps] = tfrsrivc_sep(___, Name, Value)
%
%   thm     : Matrix containing the estimated parameters. Row k contains
%             the estimates "in alphabetic order" corresponding to time k.
%   ev      : Vector of prediction errors for every recursion k.
%   Ps      : Set of parameter covariance matrices for every recursion k.
%
%   data    : The estimation data in IDDATA object format. Data can be
%             regularly or irregularly sampled.
%             For more information type "help IDDATA".
%   np      : Number of poles in the denominator.
%   nz      : Number of zeros in the numerator.
%   iodelay : Initial input-ouput time delay.
%
%   Additional estimation options can be specified through name-value pair
%   arguments. The following names are considered:
%   a. 'FF'        : Forgeting factor: FF = [ff1; ff2] where ff1 is used in
%                      the estimation of theta, while ff2 is used in the
%                      estimation of iodelay.
%                      Default: [0.99; 0.99].
%   b. 'Adg'       : Adaption gain. If the recursion number k > NumAdg, the
%                    FF or Qnvr is updated as:
%                       Qnvr = Adg * Qnvr;
%                       FF   = Adg * FF + (1 - Adg);
%                      Default: 1.
%   c. 'P0'        : Initial parameter estimation error covariance matrix.
%                      Default: I * 1e3 where I is an identity matrix.
%   d. 'NumIV'     : Recursion number when IV starts to operate.
%                      Default: N/3, where N is the total number of
%                      observations.
%   e. 'NumAdg'    : Recursion number when the adaption gain algorithm
%                    starts to operate.
%                      Default: N/3.
%   f. 'TdMax'     : Maximum time-delay boudnary.
%                      Default: inf.
%   g. 'TdMin'     : Minimum time-delay boundary.
%                      Default: 0.
%   h. 'Lambda'    : Cut-off frequency of the state variable filter (in
%                    rad/time unit).
%                      Default: 1/50 the Nyquist frequency.
%   i. 'StepMax'   : Maximum time-delay increment.
%                      Default: inf.
%   j. 'FixTd'     : Fixing the time delay: the plant model parameters are
%                    estimated by fixing the time delay.
%                      Default: 'off', can be switched to 'on'.
%   l. 'Adaption'  : Adaption law to track the time-varying parameters.
%                      Default: 'KF' (Kalman Filter), can be swithed to
%                      'FF'(forgeting factor).
%   m. 'Qnvr'     : Noise variance ratio, enabled when 'AdgLaw' is 'KF'.
%                      Default: I * 1e-3.
%   n. 'theta'    : The initial value of the vector of parameter vector:
%                   theta = [a_1, ..., a_{np}, b_0, ..., b_{nz}, IODelay]^T.
%                      Default: [0, ..., 0]^T.
%
%   References:
%   P.C. Young, "Recursive estimation and time series analysis",
%   Springer-Verlag, Berlin, Second edition, 2011.
%
%   A. Padilla, H. Garnier, P.C. Young, F. Chen and J.I. Yuz.
%   Identification of continuous-time models with slowly time-varying
%   parameters, Control Engineering Practice, 93: 104165, 2019.
%
%   F. Chen, H. Garnier, A. Padilla and M.Gilson.
%   Recursive IV identification of continuous-time models with time delay
%   from sampled data, IEEE Transactions on Control Systems Technology, to
%   be published, 2019.


