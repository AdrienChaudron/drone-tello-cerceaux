% ident_yaw_model.m
% H. Garnier 
% 04/03/2025


clear;
close all;
clc

fontsize=14;

data_raw = importdata('DataOL_Tello.txt');
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

% plot the data
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
xlabel('Time (s)')
title('Motor speed in %')
set(gca,'FontSize',fontsize)
set(findall(gcf,'type','text'),'FontSize',fontsize)


n0=1;
nf=length(Yaw);

data_est=iddata(Yaw(n0:nf)-Yaw(n0),u(n0:nf),Ts);

% Estimation of the first-order plus integrator model 'P1I' from the data
if ~isempty(which('procsrivc'))
    G=procsrivc(data_est,'P1I')
    disp('Estimated from the CONTSID toolbox')
else
    G=procest(data_est,'P1I')
    disp('Estimated from the SID toolbox')
end

K=G.Kp
T=G.Tp1

% Comparison of the model and measured yaw angle
figure
opt = compareOptions('InitialCondition', 'zero');
Yaw_sim=compare(G,data_est,opt);
grid

FIT = 100 * (1-norm(Yaw-Yaw(1)-Yaw_sim.y)/norm(Yaw-mean(Yaw)));

plot(t,Yaw-Yaw(1),'b-',t,Yaw_sim.y,'--r','linewidth',2)
title('Drone yaw angles (in °)')
xlabel('Time (s)')
legend('Measured yaw angle',['Model yaw angle ',num2str(FIT,'% 10.1f'), '%'],'location','Northeast')
set(gca,'FontSize',14,'FontName','helvetica');
xlim([0 t(end)])
ylim([-50 150])
grid
shg
