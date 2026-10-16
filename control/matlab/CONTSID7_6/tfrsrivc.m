%   TFRSRIVC estimates recursively the parameters of a continuous-time LTI
%   transfer function model with time delay using the recursive SRIVC
%   method.
%
%   Syntax:
%
%      [thm, ev, Ps] = tfrsrivc(data, np, nz)
%      [thm, ev, Ps] = tfrsrivc(data, np, nz, iodelay)
%      [thm, ev, Ps] = tfrsrivc(___, Name, Value)
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
%   a. 'FF'        : Forgeting factor.
%                      Default: 0.99.
%   b. 'Adg'       : Adaption gain of the variable forgetting factor
%                    algorithm.
%                      Default: 1.
%   c. 'P0'        : Initial parameter estimation error covariance matrix.
%                      Default: I * 1e3 where I is an identity matrix.
%   d. 'NumIV'     : Recursion number when IV starts to operate.
%                      Default: N/3, where N is the total number of
%                      observations.
%   e. 'NumVFF'    : Recursion number when the adaptive forgetting factor
%                    algorithm starts to operate.
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
%
%   References:
%   P.C. Young, "Recursive estimation and time series analysis",
%   Springer-Verlag, Berlin, Second edition, 2011.
%
%   A. Padilla, H. Garnier, P.C. Young and J.I. Yuz.
%   Real-time identification of linear continuous-time systems with slowly
%   time-varying parameters, CDC2016.
%
%   F. Chen, H. Garnier, A. Padilla and M.Gilson.
%   Recursive IV Identification of Continuous-Time Models With Time Delay
%   from Sampled Data, IEEE Transactions on Control Systems Technology, to
%   be published, 2019.


