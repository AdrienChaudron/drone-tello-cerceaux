clc
echo off

% contsid_relayfeedbacktest.m

%	H. Garnier
%   Date: 23/07/2018

%	Revision: 7.3   

k=1;
while (k~=4)
	k = menu('Model identification relay feedback test with the CONTSID',...
     'Identification by using a frequency-domain SRIVC-based method',...
 	 'Identification by using a frequency-domain PEM-based method',...
     'Quit');

   close all
	if k == 3,  break, end
    if k==1, contsid_TFFSRIVC;k=1; end
    if k==2, contsid_TFFCOE;k=1; end
    close all
end

close all
