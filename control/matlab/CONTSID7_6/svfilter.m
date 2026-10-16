%SVFILTER  defines a state-variable filter
%
% It can be based on:
%
% The normalized SVF which is given by
%
%                  lambda^n*s^k
%      L_k(s) = -----------------
%                  (s+lambda)^n
%
% The ordinary SVF which is given by
%
%                      s^k
%      L_k(s) = -----------------
%                  (s+lambda)^n
%
%   Syntax:
%
%       [b,a] = SVFILTER(lambda,n)
%       [b,a] = SVFILTER(lambda,n,type)
%
%   lambda : cut-off frequency of the SVF
%   n      : order of the SVF
%   type   : 'Normalized' (default) or 'Ordinary'
%   k      : derivative order in the numerator, i.e. num=s^k (Default: k=0)


