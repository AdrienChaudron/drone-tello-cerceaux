% Demo file for continuous-time model identification with time-delay
% Copyright:
% 		Hugues GARNIER
%       Fengwei CHEN, 27 July 2018
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

disp('    This demo shows the performance of the CONTSID Recursive')
disp('    Simplified Refined Instrumental Variable Method for')
disp('    Continuous-Time Transfer Functions (TFRSRIVC).')
disp('   ')
disp('    The TFRSRIVC method is used here to estimate a continuous-time');
disp('    output-error model with time delay from sampled data.')
disp('   ')
disp('    For further explanations see:')
disp('    F. Chen, H. Garnier, A. Padilla and M. Gilson')
disp('    "Recursive IV Identification of Continuous-Time Models With')
disp('    Time Delay from Sampled Data".')
disp('    IEEE Transactions on Control Systems Technology (2019)')
disp('    Hit any key to continue')

    echo on
    pause
    clc

%   Consider a continuous-time output-error model with time delay given by:
% 
%      y(t) = [B(s)/F(s)]u(t-8) + e(t)   
%	
% where
%	        B(s)            -4 s + 1
%	 G(s) = ---- = -----------------------------
%	        F(s)   s^3 + 2.6 s^2 + 5.29 s + 8.18

    iodelay = 7.5;
    num     = [-4 1];
    den     = [1 2.6 5.29 8.18];
    MP0     = idtf(num,den,'IODelay',iodelay)

%   Let us have a look at the step response
    step(MP0)
    title('Step response')
    
%   It can be observed from the step response that the system is strongly
%   underdamped.
     
%   Hit any key
    pause
    clc

%   The excitation signal is chosen as a PRBS sequence.

    u = prbs(8,5);
    u = repmat(u,10,1);
    u = u(:);

%   The input and output are assumed to be uniformly sampled, i.e. the
%   sampling time Ts is constant.

    Ts = 0.05;

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
 
%   Let us add white noise to the noise-free response considering a 
%   signal-to-noise ratio of 15 dB. Afterwards we plot the data.


    snr   = 15;
    e     = randn(length(u),1);
    e     = (10^(-snr/20) * std(ydet))/std(e) * e;
    data  = iddata(ydet + e,u,Ts,'Intersample','zoh');
    
%   Hit any key    

    pause
    clc
    
%   We plot the noise-free data (blue) and the data with noise (red) on a
%   zoomed part of the dataset. The presence of the time-delay is clearly 
%   noticeable since the system answers 7.5 s after the first step at time
%   40 s is sent.

    figure
    plot(datadet(400:700),'b',data(400:700),'r')
    legend('Noise-free','Noise-corrupted')
    shg
    
%   Hit any key

    pause
    clc   
    

%   Then, we estimate the model parameters by the TFRSRIVC method, which
%   takes the noise as a white one.

    np  = length(den) - 1;
    nz  = length(num) - 1;
    
%   Let us consider the following initial conditions:

    iodelay = 7.2;     % Initial time delay
    lambda  = 2;       % Breakpoint frequency of the state-variable filter
    adg     = 0.999;   % Adaption gain
    ff      = 0.99;    % Forgetting factor

    theta = tfrsrivc(data, np, nz, iodelay, 'Lambda', lambda, 'adg', adg, 'ff', ff);
        
    figure
    t = data.samplinginstants;
    plot(t,theta','linewidth',1.5)
    hold on
    plot([0,t(end)],[2.6 2.6; 5.29 5.29; 8.18 8.18; -4 -4; 1 1; 7.5 7.5]','k--')
    
    text(480,1.4,'$\hat b_1$ (1)','interpreter','latex','fontsize',11)
    text(480,-3.6,'$\hat b_0$ (-4)','interpreter','latex','fontsize',11)
    text(480,8.58,'$\hat a_3$ (8.18)','interpreter','latex','fontsize',11)
    text(480,5.69,'$\hat a_2$ (5.29)','interpreter','latex','fontsize',11)
    text(480,3.0,'$\hat a_1$ (2.6)','interpreter','latex','fontsize',11)
    text(480,7.8,'$\hat \tau$ (7.5)','interpreter','latex','fontsize',11)
    
    grid on
    
    set(gca, 'xlim', [0 t(end)], 'ylim', [-5 9])
    
    xlabel('Time (s)')
    ylabel('Parameter value')
    title('TFRSRIVC (SNR = 15 dB)')

%   Hit any key

    pause
    clc
    
    
%   Below we compare the step response of the true and estimated model 
%   by using the command STEP.

    MP1 = idtf(theta(np+1:np+nz+1,end)',[1,theta(1:np,end)'],'iodelay',theta(end,end))

    figure
    step(MP0,MP1)
    legend('True model','Estimated model by TFRSRIVC')
    set(findall(gcf,'type','text'),'FontSize',13)
    set(gca,'FontSize',13)
  
    shg
    
%   Hit any key

    pause
    clc    
%   See the help of TFRSRIVC for more explanations.

%   Hit any key
    pause
    
    echo off
    close all
    clc    


