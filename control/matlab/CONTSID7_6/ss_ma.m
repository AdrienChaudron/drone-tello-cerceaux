%ss_ma  gives a state-space representation for a moving average system.
%
%  Syntax :
%
%       [F,G,H,J] = ss_ma(C)
%
%  where C is a polynomial representating the moving average system.
%
%  ss_ma transform
%  z = Cw
%  to
%  x_k+1 = F*x_k + G*u_k
%  y_k   = H*x_k + J*u_k
%
% Reference: [Anderson 1979, p. 17]


