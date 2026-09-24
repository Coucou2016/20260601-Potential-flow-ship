clc
clear variables
close all

folder = 'path to the results folder';

fname_compt = strcat(folder, '/patchDervs.txt');
fname_exact = strcat(folder, '/exDervs.txt');
fname_ov = strcat(folder, '/ovDervs.txt');

%
fid_exact = fopen(fname_exact);
fid_compt = fopen(fname_compt);
fid_ov = fopen(fname_ov);
Compt = textscan(fid_compt, '%f %f %f %f %f %f %f %f %f %f %f %f %f', 'HeaderLines',1);
Exact = textscan(fid_exact, '%f %f %f %f %f %f %f %f %f %f %f %f %f', 'HeaderLines',1);
Ov = textscan(fid_ov, '%f %f %f %f %f %f %f %f %f %f %f %f %f', 'HeaderLines',1);

x = Compt{2};

for index=4:12
    Cp=Compt{index};
    Ep=Exact{index};
    norm = abs(max(Ep));
    Op=Ov{index};
    
    switch index
        case 4
            dertype = ' dx';
        case 5
            dertype = ' dy';
        case 6
            dertype = ' dz';
        case 7
            dertype = ' dxx';
        case 8
            dertype = ' dyy';
        case 9
            dertype = ' dzz';
        case 10
            dertype = ' dxy';
        case 11
            dertype = ' dxz';
        case 12
            dertype = ' dyz';
    end

    figure('name',dertype);

    subplot(2,2,1)
    plot(x, Cp/norm, 'kd', 'markersize',3);
    hold on
    plot(x, Ep/norm, 'gs', 'markersize',2);
    title("Derivative by OW3D")
    subplot(2,2,2)
    plot(Cp/norm, 'k-');
    hold on
    plot(Ep/norm, 'g-');
    title("Derivative by OW3D")
    %
    subplot(2,2,3)
    plot(x, Op/norm, 'kd', 'markersize',3);
    hold on
    plot(x, Ep/norm, 'gs', 'markersize',2);
    title("Derivative by Overtue")
    subplot(2,2,4)
    plot(Op/norm, 'k-');
    hold on
    plot(Ep/norm, 'g-');
    title("Derivative by Overtue")
end

