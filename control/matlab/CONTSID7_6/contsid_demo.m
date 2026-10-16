%	CONTSID toolbox 
%
%	The CONtinuous-Time System IDentification (CONTSID) toolbox is an 
%	analysis module that contains tools for building mathematical 
%	models of dynamical systems, based upon observed input-output data.
%	The toolbox contains PARAMETRIC MODELING methods which allow to directly
%	estimate CONTINUOUS-TIME linear and nonlinear models in OPEN or CLOSED
%	LOOP from UNIFORMLY or NON-UNIFORMLY SAMPLED data.
%	It is designed as an add-on to the System Identification toolbox and 
%	has a similar setup.

% 
% contsid_demo.m (former name was idcdemo.m)

%	H. Garnier 
%	$Revision: 2.0 $  Date: 02/04/2002 $ HG
%	$Revision: 3.0 $  Date: 18/06/2003 $ HG
%	$Revision: 4.1 $  Date: 07/12/2005 $ HG
%	$Revision: 5.1 $  Date: 05/07/2009 $ HG
%	$Revision: 6.0 $  Date: 09/05/2013 $ HG
%	$Revision: 7.0 $  Date: 22/10/2015 $ HG
%	$Revision: 7.2 $  Date: 23/05/2017 $ HG

clc
echo off
format compact;
p=1;
% Set the axes fonts and fontsize in all plots

UIControl_FontName_bak = get(0, 'DefaultUIControlFontName');
UIControl_FontSize_bak = get(0, 'DefaultUIControlFontSize');
UIControl_axesfontname_bak = get(0, 'Defaultaxesfontname');
UIControl_axesfontsize_bak = get(0, 'Defaultaxesfontsize');
UIControl_textfontname_bak = get(0, 'Defaulttextfontname');
UIControl_textfontsize_bak = get(0, 'Defaulttextfontsize');

set(0,'defaultuicontrolfontname','helvetica'); 
set(0,'defaultuicontrolfontsize',14);
set(0,'defaultaxesfontname','helvetica'); 
set(0,'defaultaxesfontsize',14);
set(0,'defaulttextfontname','helvetica'); 
set(0,'defaulttextfontsize',14);

help contsid_demo
disp('Hit a key to continue')
pause

while (p~=5)
 p=1;
	p = menu('CONTSID demonstration programs',...
 	 'Case Studies',...
     'Tutorials',...
     'What has the CONTSID to offer ? ',...
     'More Advanced Identification',...
     'Quit');

   close all
	if p == 5, break, end
    if p==1, contsid_case_studies;p=1; end
    if p==2, contsid_tutorials;p=1; end
    if p==3, contsid_advantages;p=1; end
    if p==4, contsid_advanced;p=1; end
    close all
end


set(0,'defaultuicontrolfontname','eval(UIControl_FontName_bak)'); 
set(0,'defaultaxesfontname','eval(UIControl_axesfontname_bak)'); 
set(0,'defaulttextfontname','eval(UIControl_textfontname_bak)'); 


close all
