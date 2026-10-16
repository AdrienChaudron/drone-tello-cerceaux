% contsid_tutorials5.m
%
% Demo file for Continuous-time Model identification from step response data
%
% Copyright:
% 		Hugues GARNIER
%	    Arturo PADILLA, March 2015

echo off
clear all
clc
close all

disp(' ')
disp(' ')
disp('                CONTINUOUS-TIME MODEL IDENTIFICATION ')
disp('                     with the CONTSID toolbox')
disp('               --------------------------------------')
disp(' ')

disp('   This demo shows the performance of the CONTSID Simple Refined')
disp('   Instrumental Variable Method for continuous-time simple PROCesses')
disp('   (PROCSRIVC)')
disp('  ')
disp('   The PROCSRIVC method is used here to estimate a continuous-time');
disp('   system from regularly sampled step response data.')
disp('  ')
disp('   Hit any key to continue')

pause
clc
echo on

%   Create a process model with an underdamped pair of complex poles and a 
%   time delay.
%   Set the initial value of the model to the following: 
%
%                     2
%   M0(s) =--------------------------   e^{-0.7*s}
%            1 + 2 *0.1*10 s + 10s^2
% 
    pause
    clc    
% 
%   Create a process model with the specified structure. 
%
%   The input argument|'P2DU'| specifies an underdamped pair of poles and a
%   time delay. The display shows that |M0| has the desired structure. The
%   display also shows that the four free parameters, |Kp|, |Tw|, |Zeta|,
%   and |Td| are all initialized to |NaN|.  
    M0 = idproc('P2DU') 
    pause
    clc    
% 
%   Set the initial values of all parameters to the desired values, that is 
%   a steady-state gain of 2, a natural frequency wn=20 rad/s (so that
%   Tw=1/wn), a damping factor z=0.1 and a time-delay of 0.7 
    M0.Kp = 2;
    M0.Tw = 1/20; %10
    M0.Zeta = 0.1;
    M0.Td = 0.7; 

    M0
    pause
    clc    
    
%   We consider that the input and output are uniformly sampled, i.e.
%   the sampling time Ts is constant.
    Ts = 0.01;

%   The input is a step sent after 30 samples to make it appear more clearly.
    u = [zeros(30,1); ones(300,1)];

%   We then create a DATA object for the input signal with no output,
%   the input u and sampling interval Ts. Additionally, the input
%   intersample behaviour is specified by setting the property
%   'Intersample' to 'zoh' since the input is piecewise constant here.
    datau = iddata([],u,Ts,'InterSample','zoh');

%   Hit any key
    pause
    clc      
    
%   The noise-free output is simulated with the SIMC routine and stored in ydet.
%   We then create a data object with output ydet, input u and sampling interval Ts.
    ydet = simc(M0,datau);
    datadet = iddata(ydet,u,Ts,'InterSample','zoh');

%   Let us add noise to the noise-free response considering a
%   signal-to-noise ratio of 15 dB. 
    y = simc(M0,datau,15);
    data = iddata(y,u,Ts,'Intersample','zoh');

%   Hit any key
    pause
    clc    
    
%   We plot the noise-free data (blue) and the noisy data (red).
    plot(datadet,'b',data,'r')
    legend('Noise-free data','Noisy data')
    set(findall(gcf,'type','text'),'FontSize',14)
    set(gca,'FontSize',14,'FontName','helvetica');

%   Hit any key
    pause
    close
    clc      

%   Parameter estimation using PROCSRIVC:
%   We will identify a continuous-time simple process model for this system
%   from the noisy data object with the PROCSRIVC algorithm. The extra
%   information required is the model type, which in this case is P2UD, i.e.
%   the model has 2 underdamped poles (P2U) and a time-delay (D). 
    init_sys = idproc('P2UD');
    M = procsrivc(data,init_sys)

%   Hit any key
    pause
    clc    
    
%   Let us now compare the estimated model parameters with the true ones 
    param_est = getpvec(M);
    param_true = getpvec(M0);
    echo off
    disp('   True TF parameters          Estimated TF parameters');
    fprintf('   %10.2f    %10.2f\n', [param_true(1:3)'; param_est(1:3)']);
    disp('   True time-delay          Estimated time-delay');
    fprintf('   %10.2f    %10.2f\n', [param_true(4); param_est(4)]);   
    echo on
    
%   The estimated parameters are clearly close to the true ones.
%   Hit any key
    pause
    clc
    
%   Let us compare the output of the estimated model with the
%   noisy output using the command COMPAREC.
    comparec(data,M);
    shg 
%   The fit is clearly very good.    
%   Hit any key
    pause
    
    echo off
    close all
    clc

