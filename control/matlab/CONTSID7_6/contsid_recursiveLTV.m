clear all
close all
clc
echo on

% 
% 
%                 Recursive identification of LTV systems
%                      with the CONTSID toolbox
%                --------------------------------------
% 
%   The CONTSID toolbox provides the following recursive LS or IV-based
%   SVF algorithms for online estimation of slowly linear time-varying 
%   continuous-time models:
%    - RLSSVF (Recursive LS-SVF)
%    - RIVSVF (Recursive IV-SVF)
%    - RSRIVC (Recursive SRIVC)
%   Two adaptation mechanisms are available for each of the algorithm
%    - Kalman filter where it is assumed that the variations of the true 
%      parameters are described by a stochastic random walk-model 
%    - Forgetting factor
%   
%   The use of the 3 recursive algorithms with the Kalman filter adaptation 
%   mechanism is illustrated in this demo. The assumed random-walk model
%   presents the advantage of easily handle the case of model parameters 
%   with different types of variations as seen below.
%   
%   The numerical example is taken from:
%   A. Padilla, H. Garnier, P.C. Young, J. Yuz. "Real-time identification 
%   of linear continuous-time systems with slowly time-varying parameters",
%   IEEE Control and Decision Conference, Las Vegas USA, 2016.
%  

%   Hit any key
    pause
    clc  

%   Consider the following continuous-time SISO second order system without
%   delay :
%	
%	   (p^2 + a1(t)p + a2(t))x(t) = b0(t)*u(t)
%
%                          y(t_k) = x(t_k) + e_0(t_k)
%
%   where p is the differentiation operator, p=d/dt.
%
%   The output of this linear time-varying system will be generated later
%   using a Simulink model.

%   Hit any key
    pause
    clc  

%   We will now define some variables that we require to run the Simulink
%   model.

    Ts = 0.01;
    tend = 1000;
    t = (0:Ts:tend)';
    N = length(t);
    % turning off warning from idinput
    warning('off','Ident:dataprocess:idinput7'); 
    u = idinput(N,'prbs',[0 0.1],[-1 1]);
    udata.signals.values = u;
    udata.time = t;
    vare = 1e-1;
    seed_nr = randi(1e4,1);
    a1 = linspace(5,45,N)';
    a2 = 160 - 90*cos(2*pi/1000*t);
    b0 = linspace(200,200,N)';
    thm0 = [a1 a2 b0];
    thm0data.signals.values = thm0;
    thm0data.time = t;    

%   "Ts" is the sampling period and "t" is the time vector. The system will
%   be excited by a Pseudo-Random Binary Sequence (PRBS) "u" stored  
%   together with the time vector "t" in "udata". White noise with variance
%   "vare" is added to the output. 

%   Hit any key
    pause
    clc  

%   Let us generate the data that will use to track the time-varying parameters 
%   by recursive estimation.

%   Hit any key
%   Please wait while Simulink is opening
    pause
    clc  
    sim('sys_coe120.slx');
    
%   Hit any key
    pause
    clc  

%   Let's store the following results obtained from the Simulink file:
%   - y  : output signal
%   - u  : input signal
%   - y0 : noise-free output signal

    y  = DS(:,1);
    u  = DS(:,2);
    y0 = DS(:,3);

%   Hit any key
    pause
    clc

%   Let's plot the true parameter values as a function of the time.    
    
%   Hit any key
    pause
    clc    

    close all
    figure
    subplot(3,1,1)
    plot(t,thm0(:,1),'r')
    ylabel('a_1')
    ylim([0 50])
    title('Time-varying parameters to be identified');
    subplot(3,1,2)
    plot(t,thm0(:,2),'r')
    ylabel('a_2')
    ylim([0 300])
    subplot(3,1,3)
    plot(t,thm0(:,3),'r')
    ylabel('b_0')
    xlabel('t (s)')
    ylim([150 250])
    
%   Note that the slow parameter variations are different.
%   a_1(t) varies slowly between 5 and 45 in a linear fashion, 
%   b_0(t) remains constant while a_2(t) varies slowly in a sine fashion.
    
    
%   Hit any key
    pause
    clc    
%   We can plot additionally the Bode diagrams of the frozen systems with the 
%   the routine bode4frozensys (see the routine help for description of  
%   input arguments).
%   The black responses are for the system at the initial time t_1 and the red  
%   responses for the system at the final time t_N. The curves in blue are for  
%   the systems in between. From this figure we can see for instance that 
%   not only the DC gain is varying but also the system bandwidth.
    bode4frozensys(thm0,[2 1],'w',logspace(-2,3));
    
%   Hit any key
    pause

%   In this example, as a consequence of the time-varying parameters, the
%   DC gain is decreasing towards half of the simulation time; and since 
%   the noise variance is kept constant, the signal-to-noise ratio (SNR) is
%   decreasing around half of the simulation time. Here you can see the
%   input/output data for t=[500,510] s, which is when the SNR is at
%   the lowest level. The noise-free output is also plotted to have an idea 
%   about the noise contribution.
    
    close all
    subplot(211)
    plot(t,y,'b',t,y0,'r');
    ylabel('y')
    xlim([500 510])
    subplot(212)
    plot(t,u,'b');
    ylabel('u');
    xlabel('t (s)')
    xlim([500 510])

%   Hit any key
    pause
    clc
    
%   We can now use the recursive least squares state-variable filter 
%   (RLSSVF) algorithm to estimate the time-varying parameters of the
%   system. Then, the following input arguments required to run the 
%   estimation routine are defined:
%   - data : data object considering the sampling interval Ts of 0.01 s.
%   - nn : number of parameters to be estimated for each polynomial.
%   - lambda_svf : cut-off frequency of the State Variable Filter.
%   - Qn : normalized covariance matrix (also called noise-variance ratio
%          matrix) given by Qn = Qw/sigma_e^2 where Qw is covariance matrix
%          of the random walk model and sigma_e^2 is the variance of the
%          noise.
%   Qw is usually set as a diagonal matrix, i.e. 
%   Qw = diag(sigma_1^2, sigma_2^2, ... , sigma_d^2) where sigma_i^2 is the
%   mean square of the rate of change of th_i(t). 
%   Therefore, when a parameter is known to be constant, the corresponding
%   value in Qn should be set close or equal to zero.

    data = iddata(y,u,Ts,'InterSample','zoh');
    nn=[2 1 0]; % nn=[na nb nk]
    lambda_svf = 16;
    Qn = diag([1e-5 1e-4 1e-10]);
    
%   Hit any key
%   Please wait while the parameters are recursively estimated    
    pause
    clc
    
    thm1 = rlssvf(data,nn,'lambda_svf',lambda_svf,'adm','kf','adg',Qn);

%   Hit any key
    pause
    clc
    
%   Let us plot the RLSSVF estimates together with the true values.    
    
%   Hit any key
    pause
    clc    

    close all
    figure
    subplot(3,1,1)
    plot(t,thm0(:,1),'r',t,thm1(:,1),'b')
    ylabel('a_1')
    legend('true','estimate','Location','NorthWest')
    legend boxoff
    ylim([0 50])
    title('RLSSVF estimates of the LTV system');
    subplot(3,1,2)
    plot(t,thm0(:,2),'r',t,thm1(:,2),'b')
    ylabel('a_2')
    ylim([0 300])
    subplot(3,1,3)
    plot(t,thm0(:,3),'r',t,thm1(:,3),'b')
    ylabel('b_0')
    xlabel('t (s)')
    ylim([150 250])
      
%   Here we can see that RLSSVF does not provide reasonable parameter 
%   estimates. In the LTI case, it is known that the RLSSVF estimates are
%   always biased due to the noise. Even though the bias cannot be totally
%   cancelled, it can be reduced by a proper choice of the cut-off frequency
%   lambda_svf. In the LTV case, this is more difficult since the system 
%   bandwidth is varying while the SVF bandwidth remains constant.
    
%   Hit any key
    pause
    clc  
    
%   A first solution to get a better tracking of the parameter estimates
%   is to use the recursive instrumental variable state-variable 
%   filter (RIVSVF) method. 
%   RIVSVF is initialized with RLSSVF. RIVSVF should start to operate at a 
%   time instant tsiv which is when RLSSVF has converged. The convergence
%   of RLSSVF can be checked by running this algorithm and comparing the
%   measured output y with the estimated output yh. yh is the second output
%   argument of the estimation routines. Here, RIVSVF is started at
%   tsiv=10 s.
%   By default, the auxiliary model used to generate the instrument is 
%   updated at every recursion. To reduce the computational load, it can be 
%   update in a period way with a period dtupdate, which here is set to 10 s.

%   Hit any key
    pause
    clc
    
    thm2 = rivsvf(data,nn,'lambda_svf',lambda_svf,'adm','kf','adg',Qn, ...
        'tsiv',10,'dtupdate',10);

    figure
    subplot(3,1,1)
    plot(t,thm0(:,1),'r',t,thm2(:,1),'b')
    ylabel('a_1')
    legend('true','estimate','Location','NorthWest')
    legend boxoff
    ylim([0 50])
    title('RIVSVF estimates of the LTV system');
    subplot(3,1,2)
    plot(t,thm0(:,2),'r',t,thm2(:,2),'b')
    ylabel('a_2')
    ylim([0 300])
    subplot(3,1,3)
    plot(t,thm0(:,3),'r',t,thm2(:,3),'b')
    ylabel('b_0')
    xlabel('t (s)')
    ylim([150 250])

%   We can see that the results are better than the ones obtained with the
%   RLSSVF method. 
%   A second solution to get a better tracking is to use the recursive 
%   simplified refined instrumental variable method for continuous-time 
%   model estimation (RSRIVC).  Notice that the routine assumes an COE
%   model, then nn and Qn must be redefined.
%   By default, the auxiliary model and prefilter are updated at every 
%   recursion. To reduce the computational load, this can be done 
%   periodically with a period dtupdate, which in this case is set to 10 s.

%   Hit any key
    pause
    clc

    nn = [1 2 0];
    Qn = diag([1e-10 1e-5 1e-4]);
    thm3 = rsrivc(data,nn,'lambda_svf',lambda_svf,'adm','kf','adg',Qn, ...
        'tsiv',10,'dtupdate',10);

    figure
    subplot(3,1,1)
    plot(t,thm0(:,1),'r',t,thm3(:,2),'b')
    ylabel('a_1')
    legend('true','estimate','Location','NorthWest')
    legend boxoff
    ylim([0 50])
    title('RSRIVC estimates of the LTV system');
    subplot(3,1,2)
    plot(t,thm0(:,2),'r',t,thm3(:,3),'b')
    ylabel('a_2')
    ylim([0 300])
    subplot(3,1,3)
    plot(t,thm0(:,3),'r',t,thm3(:,1),'b')
    ylabel('b_0')
    xlabel('t (s)')
    ylim([150 250])
    
%   Observe that the RSRIVC parameter variance for a1 and a2 in comparison 
%   with RIVSVF has been reduced due to the adaptive prefiltering.

%   Hit any key to finish
    pause
    
echo off
close all
clc
