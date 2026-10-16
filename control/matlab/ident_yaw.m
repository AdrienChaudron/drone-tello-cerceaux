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

%% Yaw Model reference => used to determine K_p_ref and K_d_ref, according to D1 and tm goals

D1 = 0.25;
tm = 1.3;
p0 = 0;

m_ref = sqrt(log(D1)^2 / (pi^2 + log(D1)^2));
K_cl_ref = 0.1;
w_0_ref = pi / (tm * sqrt(1 - m_ref^2));

% P type
K_p_yaw_ref = (tau * w_0_ref^2) / K;
K_d_yaw_ref = 0;
K_i_yaw_ref = 0;

% PD type
%K_p_yaw_ref = (tau * w_0_ref^2) / K;
%K_d_yaw_ref = (1 - 2 * m_ref * tau * w_0_ref) / K;
%K_i_yaw_ref = 0;

% PID type
%K_p_yaw_ref = (tau * (w_0_ref^2 + 2 * m * w_0_ref * p0)) / K;
%K_d_yaw_ref = (tau * (2 * m_ref * tau * w_0_ref + p0) - 1) / K;
%K_i_yaw_ref = (p0 * tau * w_0_ref^2) / K;

fprintf('\n========================================\n');
fprintf('     YAW REFERENCE MODEL PARAMETERS     \n');
fprintf('========================================\n');
fprintf('  Damping ratio (m_ref)   : %8.4f\n', m_ref);
fprintf('  Nat. frequency (w_0_ref): %8.4f rad/s\n', w_0_ref);
fprintf('----------------------------------------\n');
fprintf('  Proportional Gain (Kp)  : %8.4f\n', K_p_yaw_ref);
fprintf('  Derivative Gain   (Kd)  : %8.4f\n', K_d_yaw_ref);
fprintf('  Integral Gain     (Ki)  : %8.4f\n', K_i_yaw_ref);
fprintf('========================================\n\n');

%corr_yaw_PD = K_p_z_ref ;%+ K_d_ref * s;
%sys_yaw_ref_sim = feedback(corr_yaw_PD * sys_yaw_sim, 1);
%yaw_ref_sim = lsim(sys_yaw_ref_sim, command_yaw_uniform, time_uniform);

K_p = 2.;
K_d = 0;
K_i = 0;
corr_PID = K_p + K_d * s + K_i / s;
sys_yaw_sim_cl = feedback(corr_PID * sys_pos, 1);
yaw_sim = lsim(sys_yaw_sim_cl, command_yaw_uniform, time_uniform);

figure('Color', 'w');
plot(time_unique(idx_real), yaw_unique(idx_real), 'b-', 'LineWidth', 1.5, 'DisplayName', 'Real z');
hold on;
plot(time_uniform(idx_sim), yaw_sim(idx_sim), 'r--', 'LineWidth', 1.5, 'DisplayName', 'Simulated Z');
hold on;
plot(time_uniform(idx_sim), yaw_ref_sim(idx_sim), 'r-', 'LineWidth', 1.5, 'DisplayName', 'Ref Z');
hold on;
plot(time_unique(idx_real), command_yaw(idx_real), 'g-', 'LineWidth', 1.5, 'DisplayName', 'Command');
hold off;
grid on;
xlabel('Time [s]');
ylabel('yaw [...]');
title('Close Loop Response: Real vs. Simulated yaw');
legend('Location', 'best');