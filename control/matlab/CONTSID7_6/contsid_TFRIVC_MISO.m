% Demo file for multiple-input single-output Continuous-time Model
% identification with time delays
% Copyright:
% 		Hugues GARNIER
%       Fengwei CHEN, 22 July 2019
%


echo off
clear
clc
close all
 
clc
disp(' ')
disp(' ')
disp('                CONTINUOUS-TIME MODEL IDENTIFICATION ')
disp('                     with the CONTSID toolbox')
disp('               --------------------------------------')
disp(' ')

disp('    This demo compares the performance of the TFSRIVC and TFRIVC methods')
disp('    to estimate a two-input one-output continuous-time (MISO)')
disp('    transfer functyion plus time-delays transfer function model ')
disp('    from colored output measurement noise (Box-Jenkins model).')
disp('   ')
disp('    Hit any key to continue')

    echo on
    pause
    clc

%   Consider a two-input single-output continuous-time hybrid Box-Jenkins
%   system with time-delay given by:
% 
%      y(t) = G1(s)u(t - 4.4) + G2(s)u(t - 5.5) + [C(q)/D(q)]e(t)   
%	
% where
%	         B1(s)            5
%	 G1(s) = ----- =  -----------------
%	         F1(s)      s^2 + 2.8s + 4
% 
%	         B2(s)        3
%	 G2(s) = ----- =  ---------
%	         F2(s)      p + 2
% 
% 
%	        C(q)            1 + 0.27q^(-1)
%	 H(q) = ---- =  ------------------------------
%	        D(q)      1 - 1.98q^(-1) + 0.98q^(-2)

    num     = {5,3};
    den     = {[1 2.8 4],[1 2]};
    iodelay = [4.4,5.5];
    MP0     = idtf(num,den,'IODelay',iodelay)

%   Let us have a look at the step response
    step(MP0)
    title('Step response')
    
%   It can be observed from the step response that the second-order
%   subsystem is slighty underdamped.
     
%   Hit any key
    pause
    clc

%   The excitation signals are chosen as two PRBS sequences.

    u1 = prbs(8,10);
    u2 = prbs(7,20);
    if length(u1) >= length(u2)
        u = [u1(1 : end - length(u1) + length(u2)),u2];
    else
        u = [u1,u2(1 : end - length(u2) + length(u1))];
    end
    

%   The input and output are assumed to be uniformly sampled, i.e. the
%   sampling time Ts is constant.

    Ts = 0.1;

%   We then create a DATA object for the input signals with no output, 
%   the inputs u and sampling interval Ts. Additionally, the input
%   intersample behaviour is specified by setting the property
%   'Intersample' to 'zoh' since the input is piecewise constant here.

    datau = iddata([],u,Ts,'InterSample',{'zoh';'zoh'});

%   The noise-free output is simulated with the SIMC routine and stored in 
%   ydet. We then create a data object with output ydet, inputs u and 
%   sampling interval Ts.     

    ydet    = simc(idpoly(MP0),datau);
    datadet = iddata(ydet,u,Ts,'Intersample',{'zoh';'zoh'});
 
%   Let us add  discrete-time ARMA noise to the noise-free response. 
%   The variance of colored the noise is adjusted to get a signal-to-noise 
%   ratio of 15 dB. Afterwards we plot the data.

    C     = [1 0.2679];
    D     = [1 -1.98 0.9802];

    snr   = 15;
    e     = filter(C,D,randn(length(u),1));
    e     = (10^(-snr/20) * std(ydet))/std(e) * e;
    data  = iddata(ydet + e,u,Ts,'InterSample',{'zoh';'zoh'});
   
%   Hit any key    

    pause
    clc
    
%   We plot the noise-free data (blue) and the data with noise (red) on a
%   zoomed part of the dataset. 

    figure
    plot(datadet(400:700),'b',data(400:700),'r')
    legend('Noise-free','Noise-corrupted')
    shg
    
%   Hit any key

    pause
    clc   
    

%   Then, we first estimate the MISO model by the TFSRIVC method, where the
%   measurement noise is assumed to be white. We can therefore expect to 
%   unbiased but non-minimum variance estimates.

    np  = [length(den{1}) - 1 length(den{2}) - 1];
    nz  = [length(num{1}) - 1 length(num{2}) - 1];

    MP1 = tfsrivc(data,np,nz,'NumTd',[10,5])
    
    %   Hit any key

    pause
    
%   To reduce the variance of the parameter estimates, we should model and
%   estimate the noise contribution.
%   This can be done by using the TFRIVC algorithm where an ARMA model can be
%   specified to model the noise. 
%   Assuming that the noise is modeled as the correct (2,1) DT ARMA model, 
%   the TFRIVC is called by the statement

    nd = length(D) - 1;
    nc = length(C) - 1;
    
    [MP2,MN] = tfrivc(data,np,nz,'NN',[nd,nc],'NumTd',[10,5]);
    MP2
    
%   As expected, more accurate results are obtained. 
    
%   Hit any key

    pause
    clc
    
%   The estimated noise model takes the form

    MN
    
%   While the true noise model is 

    tf(C,D,Ts)
    
%   Hit any key

    pause
    clc
    
%   Below we compare the step response of the true and estimated model 
%   by using the command STEP.

    close 
    step(MP0,MP1,MP2)
    legend('True model','Estimated TFSRIVC model',...
        'Estimated TFRIVC model')
    shg
    
%   Hit any key

    pause
    clc    
%   See the help of TFSRIVC and TFRIVC for more explanations.

%   Hit any key
    pause
    
    echo off
    close all
    clc    


