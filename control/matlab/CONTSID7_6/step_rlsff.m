function [th,yh,P] = step_rlsff(y,phi,th,P,ff)

K = P*phi/(ff + phi'*P*phi);
P = (P - K*phi'*P)/ff;
yh = phi'*th;
th = th + K*(y - yh);