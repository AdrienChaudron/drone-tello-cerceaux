% contsid_advantage22.m
%
% Demo file for Continuous-time Model identification with time-delay
% Copyright:
% 		Hugues GARNIER
%	    Arturo PADILLA, June 2015

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
disp('   Instrumental Variable Method for Continuous-Time Simple Processes')
disp('   (PROCSRIVC)')
disp('  ')
disp('   The PROCSRIVC method is used here to estimate a continuous-time');
disp('   system with time-delay from IRREGULARLY sampled data.')
disp('  ')
disp('   Hit any key to continue')

pause
clc
echo on

%   Let us consider a continuous-time second order system with DC gain 
%   of 2, a natural frequency wn=20 rad/s and a damping factor z=0.1 plus 
%   a time-delay of 0.7
     K = 2; wn = 20; z = 0.1; Td = 0.7;
%
%   We create first a polynomial model that will be used to generate the data 
    [num,den] = ord2(wn,z);
    B = K*wn^2*num; F = den;
    M0 = idpoly(1,B,1,1,F,0,0,'InputDelay',Td)
pause
clc
%   We also create a process model that will be useful to compare the true 
%   and estimated models 
    M0proc = idproc('P2DU') 
    
%   The input |'P2DU'| specifies an underdamped pair of poles and a
%   time delay. The display shows that |M0proc| has the desired structure. 
%   It also shows that the four free parameters, |Kp|, |Tw|, |Zeta|, and |Td| 
%   are all initialized to |NaN|.  

%   Set the values of all parameters to the desired values. 
    M0proc.Kp = K;
    M0proc.Tw = 1/wn;
    M0proc.Zeta = z;
    M0proc.Td = Td; 

%   Hit any key
    pause
    clc

%   The input is chosen as a step sent after 0.3 s.
    u = [zeros(30,1); ones(300,1)];

%   First we consider that the input and output are uniformly sampled i.e.
%   the sampling time Ts is constant.
    Ts = 0.01;

%   We then create a DATA object for the input signal with no output,
%   the input u and sampling interval Ts. Additionally, the input
%   intersample behaviour is specified by setting the property
%   'Intersample' to 'zoh' since the input is piecewise constant here.
    datau = iddata([],u,Ts,'InterSample','zoh');

%   The noise-free output is simulated with the SIMC routine and stored in ydet.
%   We then create a data object with output ydet, input u and sampling interval Ts.
    ydet = simc(M0,datau);
    datadet = iddata(ydet,u,Ts,'InterSample','zoh');

%    Let us add noise to the noise-free response considering a
%    signal-to-noise ratio of 15 dB. 
    y = simc(M0,datau,15);
    data = iddata(y,u,Ts,'Intersample','zoh');

%   Hit any key
    pause
    clc
    
%   We plot the noise-free data (blue) and the data with noise (red).
    plot(datadet,'b',data,'r')

%   Hit any key
    pause
    clc
    
%   To generate irregularly sampled data we use the CONTSID function
%   COMPRESS, which kepts points of the output y such that the variation
%   from a sample to the previous one is greater than Dy.
    Dy = 0.10;
    [y_comp,t_comp] = compress([y u],Ts,Dy);

%   Let us compute the minimum and maximum sampling times.
    dt = diff(t_comp);
%   The minimum and maximum sampling times are:
    echo off
    fprintf('   %10.2f    %10.2f\n', [min(dt); max(dt)]);
    echo on
    
%   Hit any key
    pause
    clc
    
%   Creating an IDDATA object using the compressed data:
    datac = iddata(y_comp(:,1),y_comp(:,2),'SamplingInstants',t_comp, ...
      'Intersample','zoh');

%   Hit any key
    pause
    clc

%   Let us compare the regularly and irregularly sampled noisy outputs.
    t=(0:size(data.y,1)-1)'*Ts;
    subplot(2,1,1)
    plot(t,data.y,'b',t_comp,datac.y,'or')
    xlabel('Time')
    ylabel('Output')
    legend('Regularly sampled  output','Irregularly sampled output')
    set(findall(gcf,'type','text'),'FontSize',13)
    set(gca,'FontSize',13)
    axis([0.7 2.7 -0.2 3.8])
    subplot(2,1,2)
    stairs(t_comp(1:end-1),diff(t_comp))
    legend('Varying sampling period')
    xlabel('Time')
    ylabel('Ts(k)')
    set(findall(gcf,'type','text'),'FontSize',13)
    set(gca,'FontSize',13)
    axis([0.7 2.7 0 0.08])

%   Hit any key
    pause
    clc  
  
%   We will identify a continuous-time simple process model for this system
%   from the data object datac with the PROCSRIVC algorithm. The extra
%   information required is the model type, which in this case is P2D, i.e.
%   the model has 2 underdamped poles (P2+U) and a time-delay (D). 

    init_sys = idproc('P2DU');
    M = procsrivc(datac,init_sys)

%   Let us compare this estimated process model with the true one    
    pause
    M0proc
%    
%   The estimated parameters are clearly close to the true ones.    
%   Hit any key
    pause
    clc    
    
%   To compare the estimated model with the true system defined as transfer
%   function (through the command IDPOLY), we can transform the estimated
%   model into a transfer function model (Mtf) using the command IDTF.
    Mtf = idtf(M);
    param_est = getpvec(Mtf);
    param_true = [getpvec(M0)];
    echo off
    disp('   True TF parameters          Estimated TF parameters');
    fprintf('   %10.2f    %10.2f\n', [param_true'; param_est(1:3)']);
    disp('   True time-delay          Estimated time-delay');
    fprintf('   %10.2f    %10.2f\n', [M0.InputDelay; param_est(4)]);
    echo on

%   The estimated parameters are clearly close to the true ones.
%   Hit any key
    pause
    clc    
    close
    
%   Let us compute the simulated output of the model estimated from the 
%   irregularly sampled data using the command COMPAREC.

    [y,estInfo]=comparec(datadet,M);
    
%   We can then compare it to the noise-free output of the true model
    plot(t,datadet.y,'or',t,y,'b')

    title(['Coefficient of determination R_T^2=',num2str(estInfo.RT2(1,1),2)])
    xlabel('Time')
    ylabel('Output')
    legend('Output samples of the estimated model','Noisy-free true model output')
    set(findall(gcf,'type','text'),'FontSize',13)
    set(gca,'FontSize',13)
    axis([0.7 2.7 -0.2 3.8])

%   The agreement between the two outputs is very good
%   Hit any key
    pause
    
    echo off
    close all
    clc
