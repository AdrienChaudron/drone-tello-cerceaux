%% Workspace reset
clear

%% Data retrieval
data = readmatrix('../python/tello_logs/log_x.txt');

time      = data(:, 1) - 12;
target    = data(:, 2);
command   = data(:, 3);
roll      = data(:, 4);

roll_corr = roll - 0;

t_min=0;
t_max=time(end);

s = tf('s');
Ts = 0.01;

%% Plotting gotten data

fontsize=12;

figure
subplot(2,1,1)
plot(time,roll,'r','LineWidth',2),grid
title('Roll')
ylim([0 max(roll(200:end-200))+20])
xlim([t_min t_max])
set(gca,'FontSize',fontsize)
set(findall(gcf,'type','text'),'FontSize',fontsize)
subplot(2,1,2)
plot(time,target,'r','LineWidth',2),grid
title('ref roll')
ylim([min(target(200:end-200))-50 max(target(200:end-200))+50])
xlim([t_min t_max])
set(gca,'FontSize',fontsize)
set(findall(gcf,'type','text'),'FontSize',fontsize)

%% Roll open-loop estimation

K   = 0.04;
tau = 0.2;
Td  = 0.3;

num_roll = [K];
den_roll = [tau, 1];
sys_roll = tf(num_roll, den_roll, 'InputDelay', Td);

[time_unique, unique_idx] = unique(time);
command_unique            = command(unique_idx);
roll_unique               = roll_corr(unique_idx);
target_unique             = target(unique_idx);

dt = median(diff(time_unique));
time_uniform    = (time_unique(1):dt:time_unique(end))'; 
command_uniform = interp1(time_unique, command_unique, time_uniform, 'linear');
target_uniform  = interp1(time_unique, target_unique,  time_uniform, 'linear');

roll_sim_ol = lsim(sys_roll, command_uniform, time_uniform);
idx_real    = (time_unique >= t_min) & (time_unique <= t_max);
idx_sim     = (time_uniform >= t_min) & (time_uniform <= t_max);

figure('Color', 'w');
subplot(2,1,1)
plot(time_unique(idx_real), roll_unique(idx_real), 'b-', 'LineWidth', 1.5, 'DisplayName', 'Real Roll');
hold on;
plot(time_uniform(idx_sim), roll_sim_ol(idx_sim), 'r--', 'LineWidth', 1.5, 'DisplayName', 'Simulated Roll (OL)');
hold off;
grid on;
xlabel('Time [s]');
ylabel('Roll [deg]');
subplot(2,1,2)
plot(time_unique(idx_real), command(idx_real), 'g-', 'LineWidth', 1.5, 'DisplayName', 'Command');
grid on;
xlabel('Time [s]');
ylabel('Roll [deg]');
title('Open Loop Response: Real vs. Simulated Roll');
legend('Location', 'best');