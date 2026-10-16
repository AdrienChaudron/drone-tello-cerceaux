%	RELAY computes the response of a system under a relay feedback test.
%
%   Syntax
%
%       data = RELAY(num,den,Ts)
%
%   data    : Returned data in IDDATA object format, see help IDDATA.
%   den     : Denominator of the system.
%   num     : Numerator of the system.
%   Ts      : Sampling period.
%
%   Additional estimation options can be specified through name-value pair
%   arguments. The following names are considered:
%       a. 'Amp'        :   The amplitudes of the relay output. Should be
%                           Specified in the form [up,un], where up is the
%                           positive amplitude while un is the negative
%                           amplitude.
%                               Default: [1 -1]
%       b. 'Hyst'       :   The hysteresis for relay switching. Should be
%                           specified in the form [vp,vn], where vp is the
%                           positive hysterisis while en is the negative
%                           hysteresis.
%                               Default: [up un]*0.1;
%       c. 'NumCycle'   :   The number of limit cycles to be sampled.
%                               Default: 40
%       d. 'StartCycle' :   The index of limit cycle for which the sampler
%                           satrts to work. Then, the data are sampled from
%                           a sustained relay feedback oscillation.
%                               Default: 7
%       e. 'IODelay'    :   The input-output time-delay, should be an
%                           integer multiple of the sampling interval h.
%                               Default: 0
%       f. 'SNR'        :   Signal-to-noise ratio in dB. The additive noise
%                           is a white Gaussian zero-mean discrete-time
%                           noise.
%                               Default: inf
%       g. 'IntSamp'    :   Indicator for integrated sampling.
%                               Default: 'on', it can be switched to 'off'.
%


