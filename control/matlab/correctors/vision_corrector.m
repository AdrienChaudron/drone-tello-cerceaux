%% Check for ident before run
if ~exist('sys_vis_sim', 'var')
    error(['[ERROR] "sys_vis_sim" is not defined in the workspace.\n' ...
        'Please run the identification script first before executing this corrector.']);
end

% Also check parameters used in controller calculations if they were not hardcoded
if ~exist('tau_vis', 'var') || ~exist('K_vis', 'var')
    error('[ERROR] Model parameters "tau_vis" and/or "K_vis" are missing from the workspace.');
end

%% Z Model reference => used to determine K_p_ref and K_d_ref, according to D1 and tm goals

D1 = 0.25;
tm = 150;
p0 = -0.01;

m_ref = sqrt(log(D1)^2 / (pi^2 + log(D1)^2));
K_cl_ref = 1;
w_0_ref = pi / (tm * sqrt(1 - m_ref^2));

% P type
%K_p_x_ref = (tau_vis * w_0_ref^2) / K_vis;
%K_d_x_ref = 0;
%K_i_x_ref = 0;

% PD type
K_p_x_ref = (tau_vis * w_0_ref^2) / K_vis;
K_d_x_ref = (1 - 2 * m_ref * sqrt(tau_vis * w_0_ref * K_p_z_ref)) / K_vis;
K_i_x_ref = 0;

% PID type
%K_p_x_ref = (tau_vis * (w_0_ref^2 + 2 * m * w_0_ref * p0)) / K_vis;
%K_d_x_ref = (tau_vis * (2 * m_ref * tau_vis * w_0_ref + p0) - 1) / K_vis;
%K_i_x_ref = (p0 * tau_vis * w_0_ref^2) / K_vis;

fprintf('\n===============================================================\n');
fprintf('                   REFERENCE MODEL PARAMETERS                  \n');
fprintf('===============================================================\n');
fprintf('  Damping ratio (m_ref)   : %8.4f\n', m_ref);
fprintf('  Nat. frequency (w_0_ref): %8.4f rad/s\n', w_0_ref);
fprintf('---------------------------------------------------------------\n');
fprintf('  Proportional Gain (Kp)  : %8.4f\n', K_p_x_ref);
fprintf('  Derivative Gain   (Kd)  : %8.4f\n', K_d_x_ref);
fprintf('  Integral Gain     (Ki)  : %8.4f\n', K_i_x_ref);
fprintf('===============================================================\n');
fprintf('  >> NEXT STEP: Simulate closed-loop response in Simulink:\n');
fprintf('                "Simulink/SYS_CL_Z_ref.slx"\n');
fprintf('===============================================================\n\n');