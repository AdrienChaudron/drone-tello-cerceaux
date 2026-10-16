% Demo file for Continuous-time Model identification with time-delay
% Copyright:
% 		Hugues GARNIER
%       Fengwei CHEN, 22 July 2018
%
% Related papers:
%
%   Chen, F., Garnier, H., Gilson, M., "Robust identification of 
%   continuous-time models with time-delay from irregularly sampled data",
%   Journal of Process Control, 25:19-27, 2015. 
%
%   Chen, F., Zhuan, X., Garnier, H., Gilson, M., "Issuess in separable
%   identification of continuous-time models with time-delay", Automatica,
%   2018.

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

disp('    This demo shows the performance of the CONTSID Simple Refined')
disp('    Instrumental Variable Method for Continuous-Time Transfer')
disp('    Function Models (TFSRIVC).')
disp('   ')
disp('    The TFSRIVC method is used here to estimate a continuous-time');
disp('    system with time-delay from regularly sampled data.')
disp('   ')
disp('    For further explanations see:')
disp('    F. Chen, H. Garnier and M. Gilson')
disp('    "Robust identification of continuous-time models with arbitrary')
disp('    time-delay from irregularly sampled data".')
disp('    Journal of Process Control 25 (2015) 19-27')
disp('   ')
disp('    F. Chen, X. Zhuan, H. Garnier and M. Gilson')
disp('    "Issues in separable identification of continuous-time models')
disp('    with time-delay".')
disp('    Automatica (2018)')
disp('   ')
disp('    Hit any key to continue')

    echo on
    pause
    clc

%   Consider a continuous-time SISO second order system with time-delay
%   described by the following statement

    iodelay = 8;
    num     = [-4 0.5];
    den     = [1 1 4];
    M0      = idtf(num,den,'IODelay',iodelay)

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

    figure
    plot(datadet(400:700),'b',data(400:700),'r')
    shg
    
%   Hit any key

    pause
    clc   
    
%   We should be aware that identification of this system is challenging
%   since the loss function is multi-modal with respect to the time-delay.
%   To have a deeper understanding into this problem, let us show how the
%   loss function evolves with respect to the time-delay.

%   Below we fix the time-delay and using the SRIVC method to estimate the
%   model parameters. The loss function value is computed for each
%   time-delay value. 

    nz  = length(num) - 1;
    np  = length(den) - 1;
    
    tau = 0 : 0.1 : 9;
    vn  = zeros(length(tau),1);
    
    i = length(tau);
    model = tfsrivc(data,np,nz,tau(i),'FixTd','on','MaxIter',30);
    for i = length(tau) -1 : -1 : 1
        model.IODelay = tau(i);
        model = tfsrivc(data,model,'FixTd','on','MaxIter',1);
        vn(i) = model.Report.Fit.LossFcn;
        
        echo off
    end
    echo on
    
    plot(tau,vn)
    xlabel('\tau')
    ylabel('Loss function')
    grid
    
    shg
    
%   Hit any key

    pause
    clc 
    
%   It can be tested that the convergence of time-delay cannot be
%   guaranteed if poor initial time-delay is provided. For example, when
%   initial time-delay is Td0 = 2,the model estimate may not converge to
%   the optimal one.

    Td0    = 2;
    lambda = 1;
    M1     = tfsrivc(data,np,nz,Td0,'Lambda',lambda)
    
%   Hit any key

    pause
    clc 
    
%   This problem can be circumvented by exhaustive search, that is, to test
%   a set of possible time-delay values and see which is better. In the
%   Contsid toolbox the routine is TFSRIVC_INIT. 

%   By using TFSRIVC_INIT to generate an initial model, where the
%   'NumTd' property defines the number of time-delay values to be
%   tested.

    ntd        = 20;
    model_init = tfsrivc_init(data,np,nz,'NumTd',ntd)
    

    
%   Hit any key

    pause
    clc

%   Then, use model_init to initialize tfsrivc, much better results can be
%   obtained.

    M2 = tfsrivc(data,model_init) 
    
%   Hit any key

    pause
    clc
    
%   Below we compare the output of the estimated model with the sampled
%   noisy output by using the command COMPAREC.
    figure
    step(M0,M2);
    legend('True model','Estimated model')
  
    shg
    
%   Hit any key

    pause
    clc    

    
    echo off
    close all
    clc    


