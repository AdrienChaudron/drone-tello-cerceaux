% Demo file for Continuous-time Model identification with time-delay
% Copyright:
% 		Hugues GARNIER
%	    Fengwei CHEN, 15 June 2017
%       Fengwei CHEN, 23 July 2018
%
% Related papers:
%
%   Chen, F., Gilson, M., Garnier, H., Liu, T., "Robust time-domain output 
%   error method for identifying continuous-time systems with time delay",
%   Systems & Control Letters, 102:81-92, 2017.

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

disp('    This demo shows the performance of the CONTSID Output Error')
disp('    Method for Continuous-Time Systems with Time-Delay.')
disp('   ')
disp('    The TFCOE method is used here to estimate a continuous-time');
disp('    system with time-delay from regularly sampled data.')
disp('   ')
disp('    For further explanations see:')
disp('    F. Chen,  M. Gilson, H. Garnier and T. Liu')
disp('    "Robust time-domain output error method for identifying')
disp('    continuous-time systems with time delay".')
disp('    Systems & Control Letters, 102:81-92, 2017')
disp('   ')
disp('    Hit any key to continue')

    echo on
    pause
    clc

%   Consider a continuous-time SISO first order system with time delay
%   described by the following statement

    iodelay = 8;
    num     = 12;
    den     = [1 1];
    M0      = idtf(num,den,'InputDelay',iodelay)

%   Hit any key

    pause
    clc

%   The excitation signal is a PRBS sequence.

    u = prbs(12,1);

%   The input and output are assumed to be uniformly sampled, i.e. the
%   sampling time Ts is constant.

    Ts = 0.1;

%   We then create a DATA object for the input signal with no output, 
%   input u and sampling interval Ts. Additionally, the input intersample 
%   behaviour is specified by setting the property 'Intersample' to 'zoh' 
%   since the input is piecewise constant here. 

    datau = iddata([],u,Ts,'InterSample','zoh');

%   The noise-free output is simulated with the SIMC routine and stored in 
%   ydet. We then create a data object with output ydet, input u and 
%   sampling interval Ts. 

    ydet    = simc(M0,datau);
    datadet = iddata(ydet,u,Ts,'Intersample','zoh');
 
%   Let us add noise to the noise-free response considering a 
%   signal-to-noise ratio of 15 dB. Afterwards we plot the data.

    snr  = 15;
    y    = simc(M0,datau,snr);
    data = iddata(y,u,Ts,'Intersample','zoh');
    
%   Hit any key

    pause
    clc
    
%   We plot the noise-free data (blue) and the data with noise (red) on a
%   zoomed part of the dataset. The presence of the time-delay is clearly 
%   noticeable since the system answers 8s after the first step at time 40s
%   is sent. 

    plot(datadet(400:700),'b',data(400:700),'r')

%   Hit any key  

    pause
    clc    
    
%   We will identify a continuous-time model for this system from the data 
%   object with the TDCOE algorithm. The extra information required is
%   the number of numerator (B polynomial) and denominator (F polynomial)
%   parameters, i.e. np and nz.
% 
    nz = length(num) - 1;
    np = length(den) - 1;
    M  = tfcoe(data,np,nz)
    
%   The results are pretty good. Note that the iterative search is initiated 
%   (by default) by testing several time delay values in the time delay
%   range. 

%   Hit any key  

    pause
    clc
    
%   Estimation using a priori knowledge: 
%   If there is a guess about the time-delay we can specify it together 
%   with a lower and an upper bound. The true time-delay is Td = 8 and we
%   can call TDCOE considering: Td = 5. The time-delay boundaries TdMin
%   and TdMax remain the default values. 
%
%   Additionally we can specify lambda0, which is the breakpoint frequency 
%   in "rad/time unit" of the state variable filter. According to Chen et 
%   al., 2017, lambda0 should be a small value, typically 1/10 the system 
%   bandwidth

    td     = 5; 
    lambda = 0.1;
    M1     = tfcoe(data,np,nz,td,'Lambda',lambda)
    
%   The performance of the algorithm is typically unsatisfactory, as we can
%   see from the poor fit (large errors on the estimated parameters that
%   can also be observed when comparing the step responses. 
    close
    
    step(M0,M1)
    legend('True model','Estimated model without over-parametrization')
 
    shg
    
%   Hit any key  

    pause
    clc    
    
%   Applying the 'OverPar' option:
%   To increase the chance of converging to the global minimum, an over-
%   parametrization technique can be applied by using the 'OverPar' option. 

    td     = 5;
    lambda = 0.1;
    M2     = tfcoe(data,np,nz,td,'Lambda',lambda,'OverPar','on')

%   Hit any key
% 
    pause

%   The true model is
% 
    present(M0)
    
%   The fit is clearly much better
% 
    pause
    clc
    
%   The better fit can also be observed when comparing the step responses as
%   the new model response cannot be distinguished from the true.
% 
    step(M0,M2)
    legend('True model',...
        'Estimated model with over-parametrization')  
    shg

%   Hit any key
% 
    pause
    
    echo off
    close all
    clc    


