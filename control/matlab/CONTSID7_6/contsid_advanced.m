%   contsid_advanced.m

%	H. Garnier
%   Date: 23/07/2018
%	Revision: 7.0
%	Revision: 7.3

clc
echo off
k=1;

while (k~=11)
 k=1;
	k = menu('Advanced System Identification with the CONTSID',...
     'Identification of Box-Jenkins Models for Colored Measurement Noise',...
     'Identification of Transfer Function Models plus Time-delay',...
     'Identification of Transfer Function Models from Relay Feedback Test',...
 	 'Identification of Multivariable Systems',...
     'Identification of Systems Operating in Closed Loop',...
     'Identification of Errors-in-Variables (EIV) Models',...
     'Recursive Identification of Linear Time-Invariant (LTI) Models',...
     'Recursive Identification of Linear Time-Varying (LTV) Models',...
     'Identification of Linear Parameter Varying (LPV) Models ',...
     'Identification of Nonlinear Block-Structured Models',...
     'Identification of Partial Differential Equation (PDE) Models',...
     'Quit');

   close all
	if k==12, break, end
    if k==1, contsid_RIVC;k=1; end
    if k==2, contsid_TFplusDelay;k=1; end
    if k==3, contsid_relayfeedbacktest;k=1; end
    if k==4, contsid_MIMO;k=1; end
    if k==5, contsid_closedloop;k=1; end
    if k==6, contsid_EIV;k=1; end	
    if k==7, contsid_recursiveLTI;k=1; end
    if k==8, contsid_recursiveLTV;k=1; end
    if k==9, contsid_LPV;k=1; end
    if k==10, contsid_HammersteinWiener;k=1; end
    if k==11, contsid_PDE;k=1; end
    close all
end

close all
