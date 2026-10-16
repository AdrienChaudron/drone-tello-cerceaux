% Demo file for Continuous-time Model identification with time-delay
% Copyright:
% 		Hugues GARNIER
%       Fengwei CHEN, 22 July 2018
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

disp('    This demo shows the performance of the CONTSID Refined')
disp('    Instrumental Variable Method for Continuous-Time Box-Jenkins')
disp('    Transfer Function Models (TFRIVC).')
disp('   ')
disp('    The TFRIVC method is used here to estimate a continuous-time');
disp('    Box-Jenkins with time-delay from regularly sampled data.')
disp('   ')
disp('    Hit any key to continue')

    echo on
    pause
    clc

%   Consider a continuous-time hybrid Box-Jenkins system with time-delay
%   given by:
% 
%      y(t) = [B(s)/F(s)]u(t-8) + [C(q)/D(q)]e(t)   
%	
% where
%	        B(s)            4
%	 G(s) = ---- =  -----------------
%	        F(s)      s^2 + 2.8s + 4
% 
%	        C(q)            1 + 0.27q^(-1)
%	 H(q) = ---- =  ------------------------------
%	        D(q)      1 - 1.98q^(-1) + 0.98q^(-2)

    iodelay = 8;
    num     = 4;
    den     = [1 2.8 4];
    MP0     = idtf(num,den,'IODelay',iodelay)

%   Let us have a look at the step response
    step(MP0)
    title('Step response')
    
%   It can be observed from the step response that the system is slighty
%   underdamped and has unit DC-gain
     
%   Hit any key
    pause
    clc

%   The excitation signal is chosen as a PRBS sequence.

    u = prbs(8,5);

%   The input and output are assumed to be uniformly sampled, i.e. the
%   sampling time Ts is constant.

    Ts = 0.1;

%   We then create a DATA object for the input signal with no output, 
%   the input u and sampling interval Ts. Additionally, the input
%   intersample behaviour is specified by setting the property
%   'Intersample' to 'zoh' since the input is piecewise constant here.

    datau = iddata([],u,Ts,'InterSample','zoh');

%   The noise-free output is simulated with the SIMC routine and stored in 
%   ydet. We then create a data object with output ydet, input u and 
%   sampling interval Ts.     

    ydet    = simc(MP0,datau);
    datadet = iddata(ydet,u,Ts,'Intersample','zoh');
 
%   Let us add colored noise to the noise-free response considering a 
%   signal-to-noise ratio of 15 dB. Afterwards we plot the data.

    C     = [1 0.2679];
    D     = [1 -1.98 0.9802];

    snr   = 10;
    e     = filter(C,D,randn(length(u),1));
    e     = (10^(-snr/20) * std(ydet))/std(e) * e;
    data  = iddata(ydet + e,u,Ts,'Intersample','zoh');
    
%   Hit any key    

    pause
    clc
    
%   We plot the noise-free data (blue) and the data with noise (red) on a
%   zoomed part of the dataset. The presence of the time-delay is clearly 
%   noticeable since the system answers 8s after the first step at time 40s
%   is sent. 

    figure
    plot(datadet(400:700),'b',data(400:700),'r')
    legend('Noise-free','Noise-corrupted')
    shg
    
%   Hit any key

    pause
    clc   
    

%   Then, we estimate the plant model by the TFSRIVC method, which takes
%   the noise as a white one. This will generate less accurate results.

    np  = length(den) - 1;
    nz  = length(num) - 1;

    MP1 = tfsrivc(data,np,nz)
    
    %   Hit any key

    pause
    
%   To reduce the estimation error covariance, we consider noise modeling.
%   This is can be done by calling the TFRIVC method. Assuming that the
%   noise is modeled as a (2,1) DT ARMA model, the TFRIVC is called by the
%   statement

    nd = length(D) - 1;
    nc = length(C) - 1;
    
    [MP2,MN] = tfrivc(data,np,nz,'NN',[nd,nc]);
    MP2
    
%   Clearly, more accurate results are obtained. 
    
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
    close

%   Below we compare the step response of the true and estimated model 
%   by using the command STEP.

    step(MP0,MP1,MP2)
    legend('True model','Estimated TFSRIVC model',...
        'Estimated TFRIVC model','Location','best')
  
    shg
    
%   Hit any key

    pause
    clc    
%   See the help of TFRIVC for more explanations.

%   Hit any key
    pause
    
    echo off
    close all
    clc    


