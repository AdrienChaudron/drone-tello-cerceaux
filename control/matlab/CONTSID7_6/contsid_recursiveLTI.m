% contsid_recursiveLTI1.m
% 
% Demo file for Recursive Continuous-time Model identification
%

clear all
close all
clc
echo off

disp(' ')
disp(' ')
disp('                 Recursive identification of LTI systems')
disp('                     with the CONTSID toolbox')
disp('               --------------------------------------')
disp(' ')

disp('   This demo illustrates the use of recursive parameter estimation')
disp('   algorithms of continuous-time LTI models from sampled data')
disp('   with a simulated SISO example.');
disp('   Three different algorithms are used and compared.')
disp(' ')
disp('   Hit any key to continue')
pause

clc
echo on
% 
%   Consider a continuous-time SISO second order system without delay
%   described by the following transfer function:
%	
%	               2
%	 G(s) =  ---------------
%	          s^2 + 4s + 3
% 
%   Create first an IDPOLY object describing the model. The polynomials are
%   entered in descending powers of s.
    Nc=2;
    Dc=[1 4 3];
    
    M0=idpoly(1,Nc,1,1,Dc,'Ts',0);
   

%   'Ts',0 indicates that the system is time-continuous.
%   Hit any key
    pause

%   The step response.
    step(Nc,Dc)
    
%   Hit any key
    pause
    clc     

%   The Bode plot.
    bode(Nc,Dc);
     
%   Hit any key
    pause
    clc

%   We take a PRBS as input u. The sampling period is chosen to be 0.05 s.
    Ts = 0.05;
    t = (0:Ts:100)';
    N = length(t);
    u = prbs(7,8);
    u = [u;u];
    u = u(1:N);

%   We then create a DATA object for the input signal with no output, 
%   the input u and sampling interval Ts. The input intersample behaviour
%   is specified by setting the property 'Intersample' to 'zoh' since the
%   input is piecewise constant here.

    datau = iddata([],u,Ts,'InterSample','zoh');

%   For more info on DATA object, type HELP IDDATA.
%   Hit any key
    pause
    
%   The noise-free output is simulated with the SIMC routine and stored in 
%   ydet. We then create a data object with output ydet, input u and 
%   sampling interval Ts.    
    ydet = simc(M0,datau);
    datadet = iddata(ydet,u,Ts,'InterSample','zoh');
    
%   Hit any key
    pause
    
%   The input and output signals.

    plot(datadet);

%   Hit any key
    pause
    clc

%   We will now identify a continuous-time model for this system from the  
%   data object with the Recursive Least-Squares-based State-Variable 
%   Filter (RLSSVF) method. 
%   
%   The extra information required are:
%     - the number of denominator and numerator parameters and number of  
%       samples for the delay of the model [na nb nk]=[2 1 0];
%     - the "cut-off frequency (in rad/sec) of the SVF filter" set to 2 
%       rad/s here. 
%       
%   The continuous-time model identification algorithm can now be used as 
%   follows:
% 
%   Hit any key
    pause
    thm = rlssvf(datadet,[2 1 0],'lambda_svf',2);

%   Hit any key
    pause
    
%   Let us now plot the estimated parameters.

%   Hit any key
    pause
    close
    
    clc
    thm0 = repmat([Dc(2) Dc(3) Nc],N,1);
    
    close all
    figure
    subplot(3,1,1)
    plot(t,thm0(:,1),'k--',t,thm(:,1),'r')
    ylabel('a_1')
    legend('true','estimate','Location','SouthEast')
    legend boxoff
    ylim([0 6])
    title('RLSSVF estimates - Noise-free measurement case');
    subplot(3,1,2)
    plot(t,thm0(:,2),'k--',t,thm(:,2),'r')
    ylabel('a_2')
    ylim([0 6])
    subplot(3,1,3)
    plot(t,thm0(:,3),'k--',t,thm(:,3),'r')
    ylabel('b_0')
    xlabel('t (s)')
    ylim([0 6])    

%   The parameters converge very quickly to the true parameter values in
%   this noise-free measurement situation. 

%   Hit any key
    pause
    clc    

%   Consider now the case when an additive white Gaussian noise is added to
%   the output samples. The additive noise magnitude is adjusted to get a 
%   signal-to-noise ratio equal to 10 dB.

    snr=10;
    y = simc(M0,datau,snr);
    data = iddata(y,u,Ts,'InterSample','zoh');

%   The input and noisy output signals are now:
    close all
    plot(data)

%   Hit any key
    pause
    clc
    
%   Let us again use the RLSSVF routine with the previous design parameters
%   in the noisy output measurement situation.

    thm = rlssvf(data,[2 1 0],'lambda_svf',2);

%   Hit any key
    pause

%   Let us see the estimated parameters.
%   Hit any key
    pause
    
    close all
    figure
    subplot(3,1,1)
    plot(t,thm0(:,1),'k--',t,thm(:,1),'r')
    ylabel('a_1')
    legend('true','estimate','Location','SouthEast')
    legend boxoff
    ylim([0 6])
    title('RLSSVF estimates - White measurement noise');
    subplot(3,1,2)
    plot(t,thm0(:,2),'k--',t,thm(:,2),'r')
    ylabel('a_2')
    ylim([0 6])
    subplot(3,1,3)
    plot(t,thm0(:,3),'k--',t,thm(:,3),'r')
    ylabel('b_0')
    xlabel('t (s)')
    ylim([0 6])        

%   The bias on the parameters is clearly visible.

%   Hit any key
    pause
    clc    
        
%   To reduce the bias we can use instrumental variable techniques. We 
%   consider next the Recursive Instrumental Variable State-Variable Filter
%   (RIVSVF) method.
%   RIVSVF is initialized with RLSSVF. RIVSVF should start to operate at a 
%   time instant tsiv which is when RLSSVF has converged. The convergence
%   of RLSSVF can be checked by running this algorithm and comparing the
%   measured output y with the estimated output yh. yh is the second output
%   argument of the estimation routines. In this case, RIVSVF is started at
%   tsiv=10 s.
   
    thm = rivsvf(data,[2 1 0],'lambda_svf',2,'tsiv',10);

%   Hit any key
    pause
    clc
        
%   Let us see the estimated RIVSVF parameters:
    close all
    figure
    subplot(3,1,1)
    plot(t,thm0(:,1),'k--',t,thm(:,1),'r')
    ylabel('a_1')
    legend('true','estimate','Location','SouthEast')
    legend boxoff
    ylim([0 6])
    title('RIVSVF estimates - White measurement noise');
    subplot(3,1,2)
    plot(t,thm0(:,2),'k--',t,thm(:,2),'r')
    ylabel('a_2')
    ylim([0 6])
    subplot(3,1,3)
    plot(t,thm0(:,3),'k--',t,thm(:,3),'r')
    ylabel('b_0')
    xlabel('t (s)')
    ylim([0 6]) 
    set(gca,'FontSize',14,'FontName','helvetica');


    
%   The bias on the parameters has been reduced.
%   Hit any key
    pause

    
%   Although the bias has been reduced, RIVSVF is sensitive to the 
%   choice of the SVF cut-off frequency.
%   The Recursive Simplified Refined Instrumental Variable method for 
%   Continuous-time (RSRIVC) model identification is more robust against 
%   this userparameter. 
%   RSRIVC delivers optimal (unbiased + minimal variance) estimates in this
%   white noise case. RSRIVC is also initialized with RLSSVF and so the
%   user should specify the cut-off frequency of the SVF filter and the 
%   time instant tsiv when RSRIVC should start to operate.
%   Note that now the structure of the CT model to be estimated is defined 
%   as [nb nf nk] = [1 2 0], since the RSRIVC routine estimates a CT output
%   error model.
%
    thm = rsrivc(data,[1 2 0],'lambda_svf',2,'tsiv',10);

%   Hit any key
    pause

%   Let us now plot the estimated parameters.
    close all
    figure
    subplot(3,1,1)
    plot(t,thm0(:,1),'k--',t,thm(:,2),'r')
    ylabel('a_1')
    legend('true','estimate','Location','SouthEast')
    legend boxoff
    ylim([0 6])
    title('RSRIVC estimates - White measurement noise');
    subplot(3,1,2)
    plot(t,thm0(:,2),'k--',t,thm(:,3),'r')
    ylabel('a_2')
    ylim([0 6])
    subplot(3,1,3)
    plot(t,thm0(:,3),'k--',t,thm(:,1),'r')
    ylabel('b_0')
    xlabel('t (s)')
    ylim([0 6])        

%   The RSRIVC parameters converge to the true values. The convergence rate 
%   can vary depending on the noise realization. Run several the demo to get
%   an average view of the overall performance of RSRIVC.
%   Hit any key
    pause
    
%   See the help of rlssvf, rivsvf and rsrivc for more explanations.

%   Hit any key
    pause
    
echo off
close all
clc