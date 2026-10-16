%bode4fsys  bode plot for frozen systems. The first and last frozen
%  system are always plotted and they are distinguished in the legend
%  by t_1 and t_N respectively.
%
%  Syntax
%
%     bode4fsys(thm,nn,w)
%     bode4fsys(thm,nn,w,'Name',Value)
%
%  Options
%  thm : parameter vector.
%  nn = [na nb] where
%      na  : number of parameters in the A polynomial.
%      nb  : number of parameters in the B polynomial.
%
%  Additional options that can be defined as 'Name',Value pairs.
%  'w'  : vector of frequencies (in radians/TimeUnit) to evaluate the
%         frequency response. See LOGSPACE to generate logarithmically
%         spaced frequency vectors.
%         Default : w obtained from
%            [~,~,w] = bode(G1)
%         where G1 is the first frozen system.
%  'dk' : a frozen system will be plotted every dk samples. The value for
%         dk must be an integer number greater or equal to 1, otherwise
%         only the first and last frozen systems are plotted.
%         Default : (N-1)/10 where N is the number of samples.
%  'Legend' : switch the legend on or off with the values 'on' or 'off'.
%  'LegendLocation' : location of the legend in the phase plot.
%         Default : 'northeast'.


