% This script generates the Wigley hull line data, according to the
% definition in:
% "Experiments and Calculations on 4 Wigley Hull Forms in Head Waves"
%  by J.M.J. Journée, Delft University of Technology
%
% \eta=(1-\zeta^2)(1-\xi^2)(1+a_2*\xi^2+a_4*\xi^4)+\alpha*\zeta^2*(1-\zeta^8)(1-\xi^2)^4
%
% Six types are included: 'I', 'II', 'III', 'IV', 'kashi_modified', 'modified'
%
% The points for half of the geometry will be written in a text file, named after the type of the hull.
%
clc
close all
clearvars
%% input
type       = input( 'Wigley Hull type (modified_kashi, modified, I, II, III, IV or Riggs): '); % type of the Wigley Hull
L          = input('Ship length (meter): ');                  % ship length
sections   = input('Number of sections: ');                   % total number of sections
resolution = input('Number of points at each section: ');     % number of points at each section
Xo=[]; Yo=[]; Zo=[];
eta=zeros(1,resolution);
%% The elevation function
ETA = @(zeta,xi, a2,a4,alpha) (1-zeta^2)*(1-xi^2)*(1+a2*xi^2+a4*xi^4)+alpha*zeta^2*(1-zeta^8)*(1-xi^2)^4;

%% build section points
switch type
    case 'modified_kashi'
        % type characteristics
        L_B = 5;
        L_T = 2.5/0.175;
        a2 = 0.6;
        a4 = 1.0;
        alpha = 1;

        T = L/L_T;  % draft
        B = L/L_B;  % beam
        x = linspace(-L/2,L/2,sections);
        zai = 2*x/L; % non-dimensionalised x
        z = linspace(-T,0,resolution);
        zeta = z/T; % non-dimensionalised z

        for s = 1:sections
            for f = 1:resolution
                eta(f)=ETA(zeta(f),zai(s),a2,a4,alpha);
            end
            Xn = ones(resolution,1) * zai(s) * L/2;
            X = [Xo;Xn];
            Xo = X;
            Yn = eta' * B/2;
            Y = [Yo;Yn];
            Yo = Y;
            Zn = zeta' * T;
            Z = [Zo;Zn];
            Zo = Z;
        end
    case 'modified'
        % type characteristics
        L_B = 2/0.3;
        L_T = 2/0.125;
        T = L/L_T;  % draft
        B = L/L_B;  % beam
        a2 = 0.2;
        a4 = 0.;
        alpha = 1;

        x = linspace(-L/2,L/2,sections);
        zai = 2*x/L; % non-dimensionalised x
        z = linspace(-T,0,resolution);
        zeta = z/T; % non-dimensionalised z

        for s = 1:sections
            for f = 1:resolution
                eta(f)=ETA(zeta(f),zai(s),a2,a4,alpha);
            end
            Xn = ones(resolution,1) * zai(s) * L/2;
            X = [Xo;Xn];
            Xo = X;
            Yn = eta' * B/2;
            Y = [Yo;Yn];
            Yo = Y;
            Zn = zeta' * T;
            Z = [Zo;Zn];
            Zo = Z;
        end
    case 'I'
        % type I characteristics
        L_B = 10;
        L_T = 16;
        a2 = 0.2;
        a4 = 0.;
        alpha = 1;

        T = L/L_T; % draft
        B = L/L_B; % beam
        x = linspace(-L/2,L/2,sections);
        zai = 2*x/L; % non-dimensionalised x
        z = linspace(-T,0,resolution);
        zeta = z/T; % non-dimensionalised z

        for s = 1:sections
            for f = 1:resolution
                eta(f)=ETA(zeta(f),zai(s),a2,a4,alpha);
            end
            Xn = ones(resolution,1) * zai(s) * L/2;
            X = [Xo;Xn];
            Xo = X;
            Yn = eta' * B/2;
            Y = [Yo;Yn];
            Yo = Y;
            Zn = zeta' * T;
            Z = [Zo;Zn];
            Zo = Z;
        end
    case 'II'
        % type II characteristics
        L_B = 5;
        L_T = 16;
        a2 = 0.2;
        a4 = 0.;
        alpha = 1;

        T = L/L_T; % draft
        B = L/L_B; % beam
        x = linspace(-L/2,L/2,sections);
        zai = 2*x/L; % non-dimensionalised x
        z = linspace(-T,0,resolution);
        zeta = z/T;  % non-dimensionalised z

        for s = 1:sections
            for f = 1:resolution
                eta(f)=ETA(zeta(f),zai(s),a2,a4,alpha);
            end

            Xn = ones(resolution,1) * zai(s) * L/2;
            X = [Xo;Xn];
            Xo = X;
            Yn = eta' * B/2;
            Y = [Yo;Yn];
            Yo = Y;
            Zn = zeta' * T;
            Z = [Zo;Zn];
            Zo = Z;
        end
    case 'III'
        % type III characteristics
        L_B = 10;
        L_T = 16;
        a2 = 0.2;
        a4 = 0.;
        alpha = 0;

        T = L/L_T;    % draft
        B = L/L_B;    % beam
        x = linspace(-L/2,L/2,sections);
        zai = 2*x/L; % non-dimensionalised x
        z = linspace(-T,0,resolution);
        zeta = z/T; % non-dimensionalised z

        for s = 1:sections
            for f = 1:resolution
                eta(f)=ETA(zeta(f),zai(s),a2,a4,alpha);
            end
            Xn = ones(resolution,1) * zai(s) * L/2;
            X = [Xo;Xn];
            Xo = X;
            Yn = eta' * B/2;
            Y = [Yo;Yn];
            Yo = Y;
            Zn = zeta' * T;
            Z = [Zo;Zn];
            Zo = Z;
        end
    case 'IV'
        % type IV characteristics
        L_B = 5;
        L_T = 16;
        a2 = 0.2;
        a4 = 0.;
        alpha = 0;

        T = L/L_T; % draft
        B = L/L_B; % beam
        x = linspace(-L/2,L/2,sections);
        zai  = 2*x/L; % non-dimensionalised x
        z = linspace(-T,0,resolution);
        zeta = z/T; % non-dimensionalised z

        for s = 1:sections
            for f = 1:resolution
                eta(f)=ETA(zeta(f),zai(s),a2,a4,alpha);
            end
            Xn = ones(resolution,1) * zai(s) * L/2;
            X = [Xo;Xn];
            Xo = X;
            Yn = eta' * B/2;
            Y = [Yo;Yn];
            Yo = Y;
            Zn = zeta' * T;
            Z = [Zo;Zn];
            Zo = Z;
        end
    case 'Riggs'
         % type Riggs characteristics
        L_B = 10;
        L_T = 400/9;
        a2 = 0.;
        a4 = 0.;
        alpha = 0;

        T = L/L_T; % draft
        B = L/L_B; % beam
        x = linspace(-L/2,L/2,sections);
        zai  = 2*x/L; % non-dimensionalised x
        z = linspace(-T,0,resolution);
        zeta = z/T; % non-dimensionalised z

        for s = 1:sections
            for f = 1:resolution
                eta(f)=ETA(zeta(f),zai(s),a2,a4,alpha);
            end
            Xn = ones(resolution,1) * zai(s) * L/2;
            X = [Xo;Xn];
            Xo = X;
            Yn = eta' * B/2;
            Y = [Yo;Yn];
            Yo = Y;
            Zn = zeta' * T;
            Z = [Zo;Zn];
            Zo = Z;
        end

end
%% Plot
xp = [X;X];
yp = [Y;-Y];
zp = [Z;Z];
plot3(xp,yp,zp,'sb'); axis equal;
%% Write to file
fid = fopen(strcat(type,'.txt'),'w');
res=resolution;
for s=1:sections
    for p=1:res
        fprintf(fid, '%0.20f%c', X(p+res*(s-1))+L/2,',');
        fprintf(fid, '%0.20f%c', Y(p+res*(s-1)),',');
        fprintf(fid, '%0.20f\n', Z(p+res*(s-1))+T);
    end
    fprintf(fid,'\n');
end
fclose(fid);