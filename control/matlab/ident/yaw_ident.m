%% Workspace reset
clear

%% Data retrieval
data = readmatrix('./python/tello_logs/log_yaw.txt');

time      = data(:, 1);
target    = data(:, 2);
command   = data(:, 3);
yaw       = data(:, 4);

yaw_corr = yaw - 0;

t_min=0;
t_max=time(end)-10;

s = tf('s');
Ts = 0.01;

%% Plotting log data
figure
subplot(2,1,1)
plot(time,yaw,'r','LineWidth',2),grid
title('Yaw')
ylim([0 max(yaw(200:end-200))+20])
xlim([t_min t_max])
set(gca,'FontSize',fontsize)
set(findall(gcf,'type','text'),'FontSize',fontsize)
subplot(2,1,2)
plot(time,command_yaw,'r','LineWidth',2),grid
title('ref yaw')
ylim([min(command_yaw(200:end-200))-50 max(command_yaw(200:end-200))+50])
xlim([t_min t_max])
set(gca,'FontSize',fontsize)
set(findall(gcf,'type','text'),'FontSize',fontsize)

%% Yaw estimation
K_yaw = 0.95;
tau_yaw = 0.3;
Td_yaw  = 0.2;

num_yaw = [K_yaw];
den_yaw = [tau_yaw, 1];
sys_yaw_sim = tf(num_yaw, den_yaw, 'InputDelay', Td_yaw);

command_yaw_unique = command_yaw(unique_idx);
yaw_unique = yaw(unique_idx);

command_yaw_uniform = interp1(time_unique, command_yaw_unique, time_uniform, 'linear');

yaw_sim = lsim(sys_yaw_sim, command_yaw_uniform, time_uniform);
idx_yaw_real = (time_unique >= t_min) & (time_unique <= t_max);
idx_yaw_sim  = (time_uniform >= t_min) & (time_uniform <= t_max);

figure('Color', 'w');
plot(time_unique(idx_real), yaw_unique(idx_real), 'b-', 'LineWidth', 1.5, 'DisplayName', 'Real z\_speed');
hold on;
plot(time_uniform(idx_sim), yaw_sim(idx_sim), 'r--', 'LineWidth', 1.5, 'DisplayName', 'Simulated Z\_speed');
hold on;
plot(time_unique(idx_real), command_yaw(idx_real), 'g-', 'LineWidth', 1.5, 'DisplayName', 'Command');
hold off;
grid on;
xlabel('Time [s]');
title('Open Loop Response: Real vs. Simulated yaw');
legend('Location', 'best');