clc;
clear variables
close all
set(0,'defaulttextinterpreter','latex')
set(0, 'defaultAxesTickLabelInterpreter','latex');
set(0, 'defaultLegendInterpreter','latex');
%%
theta=linspace(0*pi,2*pi);
xb=20+0.5*cos(theta);
yb=0.5*sin(theta);
fid = fopen('./cylinder_ow3dt/resistance/loadtimes.txt');
while ~feof(fid)
    line = strcat('./cylinder_ow3dt/resistance/',fgetl(fid));
    data = textscan(fopen(strtrim(line)), '%f %f %f', 'HeaderLines',2);
    x = data{1};
    eta = data{3};
    [x,perm] = sort(x);
    eta = eta(perm);
    hold off
    h = plot(x, eta,'b.-','LineWidth', 1);
    [~, time, ~] = fileparts(line);
    title('$Fr = 0.6$', strcat('time(s)=',time));
    xlabel('$x/L$')
    ylabel('$\zeta/L$')
    set(gca, 'FontSize', 15);
    hold on
    plot(xb,yb,'k','LineWidth',2)
    axis equal;
    ylim([-2 2] );
    xlim([10 25]);
    grid on
    drawnow
end
