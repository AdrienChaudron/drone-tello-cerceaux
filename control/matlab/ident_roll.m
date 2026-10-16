%% Workspace reset
clear

%% Data retrieval
data = readmatrix('./python/tello_logs/log_x.txt');

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

K   = 0.1;
tau = 0.3;
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

%% Roll Model reference => used to determine K_p_ref and K_d_ref, according to D1 and tm goals

D1 = 0.15;
tm = 1.3;
p0 = -0.01;

m_ref   = sqrt(log(D1)^2 / (pi^2 + log(D1)^2));
w_0_ref = pi / (tm * sqrt(1 - m_ref^2));

% P type
% K_p_roll_ref = (tau * w_0_ref^2) / K;
% K_d_roll_ref = 0;
% K_i_roll_ref = 0;

% PD type
K_p_roll_ref = (tau * w_0_ref^2) / K;
K_d_roll_ref = (2 * m_ref * tau * w_0_ref - 1) / K;
K_i_roll_ref = 0;

% PID type
% K_p_roll_ref = (tau * (w_0_ref^2 + 2 * m_ref * w_0_ref * p0)) / K;
% K_d_roll_ref = (tau * (2 * m_ref * w_0_ref + p0) - 1) / K;
% K_i_roll_ref = (p0 * tau * w_0_ref^2) / K;

fprintf('\n========================================\n');
fprintf('       REFERENCE MODEL PARAMETERS       \n');
fprintf('========================================\n');
fprintf('  Damping ratio (m_ref)   : %8.4f\n', m_ref);
fprintf('  Nat. frequency (w_0_ref): %8.4f rad/s\n', w_0_ref);
fprintf('----------------------------------------\n');
fprintf('  Proportional Gain (Kp)  : %8.4f\n', K_p_roll_ref);
fprintf('  Derivative Gain   (Kd)  : %8.4f\n', K_d_roll_ref);
fprintf('  Integral Gain     (Ki)  : %8.4f\n', K_i_roll_ref);
fprintf('========================================\n\n');

corr_ref_PD     = K_p_roll_ref + K_d_roll_ref * s;
sys_roll_ref_cl = feedback(corr_ref_PD * sys_roll, 1);

roll_ref_sim = lsim(sys_roll_ref_cl, target_uniform, time_uniform);

K_p = 1;
K_d = 0.9;
K_i = 0;

corr_PID     = K_p + K_d * s + K_i / s;
sys_roll_cl  = feedback(corr_PID * sys_roll, 1);

roll_sim_cl = lsim(sys_roll_cl, target_uniform, time_uniform);

figure('Color', 'w');
plot(time_unique(idx_real), roll_unique(idx_real), 'b-',  'LineWidth', 1.5, 'DisplayName', 'Real Roll');
hold on;
plot(time_uniform(idx_sim), roll_sim_cl(idx_sim), 'r--', 'LineWidth', 1.5, 'DisplayName', 'Simulated Roll (Closed Loop)');
plot(time_uniform(idx_sim), roll_ref_sim(idx_sim), 'm-.', 'LineWidth', 1.5, 'DisplayName', 'Reference Model Roll');
plot(time_unique(idx_real), target(idx_real), 'k:',  'LineWidth', 1.5, 'DisplayName', 'Target');
hold off;
grid on;
xlabel('Time [s]');
ylabel('Roll [deg]');
title('Closed Loop Response: Real vs. Simulated Roll');
legend('Location', 'best');

