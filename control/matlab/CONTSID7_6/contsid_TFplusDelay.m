clc
echo off

% contsid_TFplusDelay.m

%	H. Garnier
%   Date: 25/07/2018
%	Revision: 7.3   

k=1;
while (k~=5)
	k = menu('Transfer function + delay Model Identification with the CONTSID',...
     'Identification by using the TFSRIVC routine - SISO case',...
     'Identification by using the TFRIVC routine - SISO case',...
     'Identification by using the TFCOE routine - SISO case',...
     'Identification by using the TFSRIVC routine - MISO case',...
     'Quit');

   close all
	if k == 5,  break, end
    if k==1, contsid_TFSRIVC;k=1; end
    if k==2, contsid_TFRIVC;k=1; end
    if k==3, contsid_TFCOE;k=1; end
    if k==4, contsid_TFRIVC_MISO;k=1; end
    close all
end

close all
