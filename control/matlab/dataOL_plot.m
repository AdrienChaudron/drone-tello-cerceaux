% dataOL_plot.m
% H. Garnier 
% 04/04/2024


clear;
close all;
clc

fontsize=12;

data_raw = importdata('DataOL_yaw_Tello.txt');
   %  Time.append(float(valeurs[0]))
   %  Altitude.append(float(valeurs[1]))
   %  cmd.append(float(valeurs[2]))
   %  consign.append(float(valeurs[3]))
   %  speed.append(float(valeurs[4]))

selectedColumns = data_raw(:, [1, 2, 3, 5]);

% Define input-output variables
t = selectedColumns(:,1); % time-instants
Xz = selectedColumns(:,2); % Altitude in cm
u = selectedColumns(:,3); % motor speed in %
Yaw = selectedColumns(:,4); % yaw angle in °

Ts = mean(diff(t));

xmin=0;
xmax=t(end);

figure
subplot(3,1,1)
plot(t,Xz,'r','LineWidth',2),grid
title('Drone altitude in cm')
ylim([0 max(Xz(200:end-200))+20])
xlim([xmin xmax])
set(gca,'FontSize',fontsize)
set(findall(gcf,'type','text'),'FontSize',fontsize)
subplot(3,1,2)
plot(t,Yaw,'r','LineWidth',2),grid
title('Yaw angle in °')
ylim([min(Yaw(200:end-200))-50 max(Yaw(200:end-200))+50])
xlim([xmin xmax])
set(gca,'FontSize',fontsize)
set(findall(gcf,'type','text'),'FontSize',fontsize)
subplot(3,1,3)
plot(t,u,'r','LineWidth',2),grid
xlim([xmin xmax])
ylim([min(u(200:end-200))-20 max(u(200:end-200))+20])
xlabel('Time (s)')
title('Motor speed in %')
set(gca,'FontSize',fontsize)
set(findall(gcf,'type','text'),'FontSize',fontsize)
