clc
clearvars
close all

set(0, 'defaulttextinterpreter','latex')
set(0, 'defaultAxesTickLabelInterpreter','latex');
set(0, 'defaultLegendInterpreter','latex');

fid = fopen("patch_0.interp");
data = textscan(fid, "%f %f %f %f %f" , 'HeaderLines',1);

figure(1)
subplot(3,1,1)
hold on
plot(data{1}, data{5}, 'g.')
plot(data{1}, data{4}, 'ko')
legend('Exact','Interpolated')
xlabel('$x$')
fontsize(gca, 15,'points')
%
subplot(3,1,2)
hold on
plot(data{2}, data{5}, 'g.')
plot(data{2}, data{4}, 'ko')
fontsize(gca, 15,'points')
xlabel('$y$')
%
subplot(3,1,3)
hold on
plot(data{3}, data{5}, 'g.')
plot(data{3}, data{4}, 'ko')
fontsize(gca, 15,'points')
xlabel('$z$')
%
figure(2)
hold on
plot(data{5}, 'g-')
plot(data{4}, 'k-')
legend('Exact','Interpolated')
fontsize(gca, 15,'points')
%
figure(3)
plot3(data{1}, data{2}, data{3}, 'b.')
xlabel('$x$')
ylabel('$y$')
zlabel('$z$')
fontsize(gca, 15,'points')
axis equal