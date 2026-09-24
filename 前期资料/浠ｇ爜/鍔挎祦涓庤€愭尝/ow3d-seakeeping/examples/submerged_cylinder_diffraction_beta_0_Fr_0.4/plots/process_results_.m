
clc
clear variables
close all

%%

A   = 1;
a   = 0.5;
d   = 0.5 * 2;
g   = 9.81;
rho = 1000;
h   = 2 * a;

%% READ NUMERICAL DATA

nk_file_name_frc_1         = '../cylinder_ppc/wvf1.txt';
nk_fid_frc_1 = fopen(nk_file_name_frc_1);
nk_file_name_frc_3         = '../cylinder_ppc/wvf3.txt';
nk_fid_frc_3 = fopen(nk_file_name_frc_3);

nk_data_frc_1  = textscan(nk_fid_frc_1, '%f %f %f %f %f');
nk_data_frc_3  = textscan(nk_fid_frc_3, '%f %f %f %f %f');

nu0 = ( nk_data_frc_1{1}).^2/g;

encf = nk_data_frc_1{2};

nu   = encf.^2/g;

% 
nk_frc_surge_real = nk_data_frc_1{3};
nk_frc_surge_imag = nk_data_frc_1{4};

nk_frc_heave_real = nk_data_frc_3{3};
nk_frc_heave_imag = nk_data_frc_3{4};

nk_frc_surge = sqrt(nk_frc_surge_real.^2 + nk_frc_surge_imag.^2) ./ (rho * pi * a^2 * nu0  .* exp(-nu0 * h) );

nk_frc_heave = sqrt(nk_frc_heave_real.^2 + nk_frc_heave_imag.^2) ./ (rho * pi * a^2 * nu0  .* exp(-nu0 * h) );


%%
res_index     = 1:200;

fid = fopen('processed_forces_fol.txt', 'w');

surge_amp  = nk_frc_surge(res_index);
heave_amp  = nk_frc_heave(res_index);

nua = nu0(res_index) * a;

all_dat = [ nua' ; surge_amp'; heave_amp'];

fprintf(fid, '%12s   %12s    %12s   \n', 'nua', 'surge' , 'heave');
fprintf(fid, '%15.8e %15.8e  %15.8e \n', all_dat);


fclose( 'all');