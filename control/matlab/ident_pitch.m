%% Workspace reset
clear

%% Data retrieval
data = readmatrix('./python/tello_logs/log_y.txt');

time      = data(:, 1) - 12;
target    = data(:, 2);
command   = data(:, 3);
pitch     = data(:, 4);

pitch_corr = pitch - 0;

t_min = 0;
t_max = time(end);

s  = tf('s');
Ts = 0.01;

%% Plotting gotten data

fontsize = 12;

figure('Color', 'w');
subplot(2,1,1)
plot(time, pitch_corr, 'r', 'LineWidth', 2); grid on;
title('Pitch')
ylim([0 max(pitch_corr(200:end-200)) + 20])
xlim([t_min t_max])
set(gca, 'FontSize', fontsize)
set(findall(gcf, 'type', 'text'), 'FontSize', fontsize)

subplot(2,1,2)
plot(time, target, 'r', 'LineWidth', 2); grid on;
title('Ref Pitch')
ylim([min(target(200:end-200)) - 50, max(target(200:end-200)) + 50])
xlim([t_min t_max])
set(gca, 'FontSize', fontsize)
set(findall(gcf, 'type', 'text'), 'FontSize', fontsize)

%% Pitch open-loop estimation

K   = 0.1;
tau = 0.3;
Td  = 0.3;

num_pitch = [K];
den_pitch = [tau, 1];
sys_pitch = tf(num_pitch, den_pitch, 'InputDelay', Td);

[time_unique, unique_idx] = unique(time);
command_unique            = command(unique_idx);
pitch_unique              = pitch_corr(unique_idx);
target_unique             = target(unique_idx);

dt = median(diff(time_unique));
time_uniform    = (time_unique(1):dt:time_unique(end))'; 
command_uniform = interp1(time_unique, command_unique, time_uniform, 'linear');
target_uniform  = interp1(time_unique, target_unique,  time_uniform, 'linear');

pitch_sim_ol = lsim(sys_pitch, command_uniform, time_uniform);
idx_real     = (time_unique >= t_min) & (time_unique <= t_max);
idx_sim      = (time_uniform >= t_min) & (time_uniform <= t_max);

figure('Color', 'w');
subplot(2,1,1)
plot(time_unique(idx_real), pitch_unique(idx_real), 'b-', 'LineWidth', 1.5, 'DisplayName', 'Real Pitch');
hold on;
plot(time_uniform(idx_sim), pitch_sim_ol(idx_sim), 'r--', 'LineWidth', 1.5, 'DisplayName', 'Simulated Pitch (OL)');
hold off;
grid on;
xlabel('Time [s]');
ylabel('Pitch [deg]');
title('Open Loop Response: Real vs. Simulated Pitch');
legend('Location', 'best');

subplot(2,1,2)
plot(time_unique(idx_real), command(idx_real), 'g-', 'LineWidth', 1.5, 'DisplayName', 'Command');
grid on;
xlabel('Time [s]');
ylabel('Command');
legend('Location', 'best');

%% Pitch Model reference => used to determine K_p_ref and K_d_ref, according to D1 and tm goals

D1 = 0.15;
tm = 1.3;
p0 = -0.01;

m_ref   = sqrt(log(D1)^2 / (pi^2 + log(D1)^2));
w_0_ref = pi / (tm * sqrt(1 - m_ref^2));

% P type
% K_p_pitch_ref = (tau * w_0_ref^2) / K;
% K_d_pitch_ref = 0;
% K_i_pitch_ref = 0;

% PD type
K_p_pitch_ref = (tau * w_0_ref^2) / K;
K_d_pitch_ref = (2 * m_ref * tau * w_0_ref - 1) / K;
K_i_pitch_ref = 0;

% PID type
% K_p_pitch_ref = (tau * (w_0_ref^2 + 2 * m_ref * w_0_ref * p0)) / K;
% K_d_pitch_ref = (tau * (2 * m_ref * w_0_ref + p0) - 1) / K;
% K_i_pitch_ref = (p0 * tau * w_0_ref^2) / K;

fprintf('\n========================================\n');
fprintf('    PITCH REFERENCE MODEL PARAMETERS    \n');
fprintf('========================================\n');
fprintf('  Damping ratio (m_ref)   : %8.4f\n', m_ref);
fprintf('  Nat. frequency (w_0_ref): %8.4f rad/s\n', w_0_ref);
fprintf('----------------------------------------\n');
fprintf('  Proportional Gain (Kp)  : %8.4f\n', K_p_pitch_ref);
fprintf('  Derivative Gain   (Kd)  : %8.4f\n', K_d_pitch_ref);
fprintf('  Integral Gain     (Ki)  : %8.4f\n', K_i_pitch_ref);
fprintf('========================================\n\n');

corr_ref_PD      = K_p_pitch_ref + K_d_pitch_ref * s;
sys_pitch_ref_cl = feedback(corr_ref_PD * sys_pitch, 1);

pitch_ref_sim = lsim(sys_pitch_ref_cl, target_uniform, time_uniform);

%% Pitch control => closed loop simulation

K_p = 1;
K_d = 0.9;
K_i = 0;

corr_PID      = K_p + K_d * s + K_i / s;
sys_pitch_cl  = feedback(corr_PID * sys_pitch, 1);

pitch_sim_cl = lsim(sys_pitch_cl, target_uniform, time_uniform);

figure('Color', 'w');
plot(time_unique(idx_real), pitch_unique(idx_real), 'b-',  'LineWidth', 1.5, 'DisplayName', 'Real Pitch');
hold on;
plot(time_uniform(idx_sim), pitch_sim_cl(idx_sim), 'r--', 'LineWidth', 1.5, 'DisplayName', 'Simulated Pitch (Closed Loop)');
plot(time_uniform(idx_sim), pitch_ref_sim(idx_sim), 'm-.', 'LineWidth', 1.5, 'DisplayName', 'Reference Model Pitch');
plot(time_unique(idx_real), target(idx_real), 'k:',  'LineWidth', 1.5, 'DisplayName', 'Target');
hold off;
grid on;
xlabel('Time [s]');
ylabel('Pitch [deg]');
title('Closed Loop Response: Real vs. Simulated Pitch');
legend('Location', 'best');