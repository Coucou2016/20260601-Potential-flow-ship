clc
close all
clearvars

fid_up_x = fopen("./upwind_ow3dt/updervs_dx.txt");
fid_up_z = fopen("./upwind_ow3dt/updervs_dz.txt");
data_up_x = textscan(fid_up_x, '%f %f %f %f', 'HeaderLines',1);
data_up_z = textscan(fid_up_z, '%f %f %f %f', 'HeaderLines',1);
fid_ov_x = fopen("./upwind_ow3dt/ovdervs_dx.txt");
fid_ov_z = fopen("./upwind_ow3dt/ovdervs_dz.txt");
data_ov_x = textscan(fid_ov_x, '%f %f %f %f', 'HeaderLines',1);
data_ov_z = textscan(fid_ov_z, '%f %f %f %f', 'HeaderLines',1);
x = data_up_x{1};
y = data_up_x{2};
z = data_up_x{3};
subplot(2,1,1)
plot(x, data_ov_x{4}, 'bo', x, data_up_x{4}, 'g*');
subplot(2,1,2)
plot(x, data_ov_z{4}, 'bo', x, data_up_z{4}, 'g*');