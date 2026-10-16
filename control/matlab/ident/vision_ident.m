%% Workspace reset
clear;
close all;
clc;

fontsize = 12;

%% Data retrieval
% Read the log file
data = readmatrix('./x_1791535745.csv');

time      = data(:, 1);
target    = data(:, 3);
command_x   = data(:, 3);
y_vision       = data(:, 10);

% Zero-offset correction / initial alignment
y_vision_corr = y_vision - mean(y_vision);

t_min = 0;
t_max = time(end);

s = tf('s');
Ts = 0.01; % Uniform sampling step

%% Plotting raw log data
figure('Name', 'Vision Log Data', 'NumberTitle', 'off');

subplot(2,1,1)
plot(time, y_vision_corr, 'r', 'LineWidth', 2); grid on;
title('Vision Lateral Position (b)')
xlim([t_min t_max])
xlabel('Time [s]')
ylabel('Position [m]')
set(gca, 'FontSize', 16)
set(findall(gcf, 'type', 'text'), 'FontSize', 16)

subplot(2,1,2)
plot(time, command_x, 'r', 'LineWidth', 2); grid on;
title('Command X')
xlim([t_min t_max])
xlabel('Time [s]')
ylabel('Command')
set(gca, 'FontSize', 16)
set(findall(gcf, 'type', 'text'), 'FontSize', 16)

%% Vision Model Identification (K, tau, Td)
% Model parameters to tune:
K_vis   = 0.01;  % Static gain (sign reflects direction: +X decreases b)
tau_vis = 0.5;    % Time constant [s]
Td_vis  = 0.20;    % Input delay / Dead time [s]

% --- First-Order Plus Dead Time (FOPDT) Transfer Function ---
num_vis = [K_vis];
den_vis = [tau_vis, 1];
sys_vis_sim = tf(num_vis, den_vis, 'InputDelay', Td_vis);
sys_vis_sim = sys_vis_sim / s;

% NOTE: If the drone command X controls lateral velocity rather than lateral position,
% the model contains an integrator 1/s. In that case, uncomment the line below:
% sys_vis_sim = tf(num_vis, [tau_vis, 1, 0], 'InputDelay', Td_vis);

% Remove duplicate timestamps for interp1
[time_unique, unique_idx] = unique(time);
command_x_unique = command_x(unique_idx);
y_vision_unique  = y_vision_corr(unique_idx);

% Create uniform time base
time_uniform = (t_min:Ts:t_max)';

% Interpolate input command
command_x_uniform = interp1(time_unique, command_x_unique, time_uniform, 'linear', 'extrap');

% Simulate response
y_vis_sim = lsim(sys_vis_sim, command_x_uniform, time_uniform) - 0.2;

% Time window indices
idx_vis_real = (time_unique >= t_min) & (time_unique <= t_max);
idx_vis_sim  = (time_uniform >= t_min) & (time_uniform <= t_max);

figure('Name', 'Vision Model Comparison', 'NumberTitle', 'off');

subplot(2,1,1)
plot(time_unique(idx_vis_real), y_vision_unique(idx_vis_real) + y_vision(1), 'r', 'LineWidth', 2); hold on; grid on;
plot(time_uniform(idx_vis_sim), y_vis_sim(idx_vis_sim) + y_vision(1), 'b--', 'LineWidth', 2);
title(sprintf('Vision Position: Real vs Simulated (K = %.4f, \\tau = %.2f s, T_d = %.2f s)', K_vis, tau_vis, Td_vis))
legend('Measured (b)', 'Simulated Model', 'Location', 'best')
xlim([t_min t_max])
xlabel('Time [s]')
ylabel('Position [m]')
set(gca, 'FontSize', 16)

subplot(2,1,2)
plot(time_uniform(idx_vis_sim), command_x_uniform(idx_vis_sim), 'k', 'LineWidth', 1.5); grid on;
title('Input Command X')
xlim([t_min t_max])
xlabel('Time [s]')
ylabel('Command')
set(gca, 'FontSize', 16)