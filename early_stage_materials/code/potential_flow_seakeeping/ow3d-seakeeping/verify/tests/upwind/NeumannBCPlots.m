clc
close all
clearvars
set(0,'defaulttextinterpreter','latex')
set(0, 'defaultAxesTickLabelInterpreter','latex');
set(0, 'defaultLegendInterpreter','latex');
%%
path_to_results = "./upwind_ow3dt";
fid_homb = fopen(strcat(path_to_results,"/neumann_hom_body.txt"));
fid_nhomb = fopen(strcat(path_to_results, "/neumann_nhom_body.txt"));
fid_varbxb = fopen(strcat(path_to_results, "/neumann_varbx_body.txt"));
data_homb = textscan(fid_homb, '%f %f %f %f', 'HeaderLines',1);
data_nhomb = textscan(fid_nhomb, '%f %f %f %f', 'HeaderLines',1);
data_varbxb = textscan(fid_varbxb, '%f %f %f %f', 'HeaderLines',1);
xb = data_homb{1};
zb = data_homb{3};
figure(1)
subplot(1,3,1)
plot(xb, data_homb{4}, 'g.', xb, 0*xb, 'ko');
title('$\frac{\partial \phi}{\partial n} = 0$')
set(gca, 'FontSize', 20);
ylim([-0.001 0.001])
subplot(1,3,2)
plot(xb, data_nhomb{4}, 'g.', xb, xb./xb*8.5, 'ko');
title('$\frac{\partial \phi}{\partial n} = 8.5$')
set(gca, 'FontSize', 20);
subplot(1,3,3)
plot(zb, data_varbxb{4}, 'g.', zb, xb, 'ko');
title('$\frac{\partial \phi}{\partial n} = x $')
set(gca, 'FontSize', 20);
axis equal
%%
fid_homw = fopen(strcat(path_to_results,"/neumann_hom_wall.txt"));
fid_nhomw = fopen(strcat(path_to_results,"/neumann_nhom_wall.txt"));
fid_varbxw = fopen(strcat(path_to_results, "/neumann_varbx_wall.txt"));
data_homw= textscan(fid_homw, '%f %f %f %f', 'HeaderLines',1);
data_nhomw = textscan(fid_nhomw, '%f %f %f %f', 'HeaderLines',1);
data_varbxw = textscan(fid_varbxw, '%f %f %f %f', 'HeaderLines',1);
xw = data_homw{1};
zw = data_homw{3};
figure(2)
subplot(1,3,1)
plot(xw, data_homw{4}, 'g.', xw, 0*xw, 'ko');
title('$\frac{\partial \phi}{\partial n} = 0$')
set(gca, 'FontSize', 20);
ylim([-0.001 0.001])
subplot(1,3,2)
plot(xw, data_nhomw{4}, 'g.', xw, xw./xw*8.5, 'ko');
title('$\frac{\partial \phi}{\partial n} = 8.5$')
set(gca, 'FontSize', 20);
subplot(1,3,3)
plot(zw, data_varbxw{4}, 'g.', zw, xw, 'ko');
title('$\frac{\partial \phi}{\partial n} = x $')
set(gca, 'FontSize', 20);
axis equal
