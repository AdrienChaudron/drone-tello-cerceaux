%% Workspace reset
clear

%% Data retrieval
data = readmatrix('log_z.txt');

time        = data(:, 1);
consigne    = data(:, 2);
command_z   = data(:, 3);
altitude    = data(:, 4);

z_corr = altitude - 100;

t_min=0;
t_max=time(end)-10;

s = tf('s');
Ts = 0.01;

%% Plotting gotten data

fontsize=12;

figure
subplot(3,1,1)
plot(time,altitude,'r','LineWidth',2),grid
title('Drone altitude in cm')
ylim([0 max(altitude(200:end-200))+20])
xlim([t_min t_max])
set(gca,'FontSize',fontsize)
set(findall(gcf,'type','text'),'FontSize',fontsize)
subplot(3,1,2)
plot(time,command_z,'r','LineWidth',2),grid
title('z speed')
ylim([min(command_z(200:end-200))-50 max(command_z(200:end-200))+50])
xlim([t_min t_max])
set(gca,'FontSize',fontsize)
set(findall(gcf,'type','text'),'FontSize',fontsize)
subplot(3,1,3)
plot(time,command_z,'r','LineWidth',2),grid
xlim([t_min t_max])
ylim([min(command_z(200:end-200))-20 max(command_z(200:end-200))+20])
xlabel('Time (s)')
title('Motor speed in %')
set(gca,'FontSize',fontsize)
set(findall(gcf,'type','text'),'FontSize',fontsize)

%% Z_speed estimation

K = 0.6;
tau = 0.3;
Td  = 0.3;

num_speed = [K];
den_speed = [tau, 1];
sys_speed_sim = tf(num_speed, den_speed, 'InputDelay', Td);
sys_pos = sys_speed_sim / s; 

[time_unique, unique_idx] = unique(time);
command_z_unique = command_z(unique_idx);
z_speed_unique = z_speed(unique_idx);

dt = median(diff(time_unique));
time_uniform = (time_unique(1):dt:time_unique(end))'; 
command_z_uniform = interp1(time_unique, command_z_unique, time_uniform, 'linear');

z_speed_sim = lsim(sys_speed_sim, command_z_uniform, time_uniform);
idx_real = (time_unique >= t_min) & (time_unique <= t_max);
idx_sim  = (time_uniform >= t_min) & (time_uniform <= t_max);

figure('Color', 'w');
subplot(2,1,1)
plot(time_unique(idx_real), z_speed_unique(idx_real), 'b-', 'LineWidth', 1.5, 'DisplayName', 'Real z\_speed');
hold on;
plot(time_uniform(idx_sim), z_speed_sim(idx_sim), 'r--', 'LineWidth', 1.5, 'DisplayName', 'Simulated Z\_speed');
hold off;
grid on;
subplot(2,1,2)
plot(time_unique(idx_real), command_z(idx_real), 'g-', 'LineWidth', 1.5, 'DisplayName', 'Command');
grid on;
xlabel('Time [s]');
ylabel('Speed [m/s]');
title('Open Loop Response: Real vs. Simulated z-speed');
legend('Location', 'best');

fprintf('\n===============================================================\n');
fprintf('                   POSITION MODEL (sys_pos)                    \n');
fprintf('===============================================================\n');
disp(sys_pos)
fprintf('>> [NEXT STEP]: Please refer to "correctors/z_corrector" to continue\n');
fprintf('                with controller design and simulation.\n');
fprintf('===============================================================\n\n');