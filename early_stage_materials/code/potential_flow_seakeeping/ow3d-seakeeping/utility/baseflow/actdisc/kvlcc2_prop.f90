!*****************************************************************************************
!> author: Saettone Simone
!  license: Technical University of Denmark
!  date: April 2018

   module mod_common

      use, intrinsic :: iso_c_binding

      implicit none

      ! Choose between single and double precision.
      integer, parameter :: mks = C_FLOAT
      integer, parameter :: mkd = C_DOUBLE
      integer, parameter, public :: mk = mkd

      ! Length vector of input data.
      integer, parameter :: k = 40

      ! Pi.
      real(kind=mk), parameter :: pi = 2.0_mk*asin(1.0_mk)

      ! Number of blades.
      integer, parameter :: blade_number = 4

      ! Propeller angular velocity [rad/sec]
      real(kind=mk), parameter :: omega = 7.95870_mk

      ! Ship velocity [m/sec].
      real(kind=mk), parameter :: v_ship = 7.97389_mk

      ! Propeller radius [m].
      real(kind=mk), parameter :: radius = 4.93000_mk

      ! Propeller position [m].
      real(kind=mk), parameter :: x_prop = -165.5360_mk
      real(kind=mk), parameter :: y_prop = -15.0016_mk
      real(kind=mk), parameter :: z_prop = 0.0_mk

      ! Propeller radius [-].
      real(kind=mk), dimension(k) :: r_R_prop = &
            [ 0.000_mk, 0.050_mk, 0.075_mk, 0.100_mk, 0.125_mk, 0.150_mk, 0.175_mk, &
              0.200_mk, 0.225_mk, 0.250_mk, 0.275_mk, 0.300_mk, 0.325_mk, 0.350_mk, &
              0.375_mk, 0.400_mk, 0.425_mk, 0.450_mk, 0.475_mk, 0.500_mk, 0.525_mk, &
              0.550_mk, 0.575_mk, 0.600_mk, 0.625_mk, 0.650_mk, 0.675_mk, 0.700_mk, &
              0.725_mk, 0.750_mk, 0.775_mk, 0.800_mk, 0.825_mk, 0.850_mk, 0.875_mk, &
              0.900_mk, 0.925_mk, 0.950_mk, 0.975_mk, 1.000_mk ]

      ! Propeller circulation (m2/sec).
      real(kind=mk), dimension(k) :: circ_prop = &
            [ 0.000000_mk, 0.908304_mk, 1.344410_mk, 1.768157_mk, 2.179283_mk, 2.577510_mk, 2.962543_mk, &
              3.334069_mk, 3.691756_mk, 4.035248_mk, 4.364166_mk, 4.678104_mk, 4.976624_mk, 5.259256_mk, &
              5.525491_mk, 5.774777_mk, 6.006513_mk, 6.220044_mk, 6.414648_mk, 6.589532_mk, 6.743815_mk, &
              6.876517_mk, 6.986536_mk, 7.072628_mk, 7.133378_mk, 7.167157_mk, 7.172078_mk, 7.145921_mk, &
              7.086045_mk, 6.989254_mk, 6.851608_mk, 6.668138_mk, 6.432393_mk, 6.135700_mk, 5.765841_mk, &
              5.304471_mk, 4.721412_mk, 3.959207_mk, 2.873255_mk, 0.000000_mk ]

!*****************************************************************************************

!*****************************************************************************************

   end module mod_common

!*****************************************************************************************
!> author: Saettone Simone
!  license: Technical University of Denmark
!  date: April 2018

   module mod_subroutines

      use mod_common

      private

      public :: check_data, surface_circulation, radius_dimension, compute_r, compute_q, &
                induced_axial, induced_radial, induced_tangential, cartesian_velocity, &
                move_coor

   contains

!*****************************************************************************************

!*****************************************************************************************
!>
!     Check and modify input data.

      subroutine check_data

         use mod_common

         implicit none

         ! Check input propeller radius: first value.
         if (r_R_prop(1) > (epsilon(r_R_prop(1)))) then
            print *, 'ERROR: First value of the dimensionless radius needs to be 0.0!'
            error stop
         end if

         ! Check input propeller radius: last value.
         if (r_R_prop(size(r_R_prop)) < (1.0_mk-epsilon(r_R_prop(size(r_R_prop))))) then
            print *, 'ERROR: Last value of the dimensionless radius needs to be 1.0!'
            error stop
         end if

         ! Modify first value propeller radius.
         if (r_R_prop(1) <= epsilon(r_R_prop(1))) then
            r_R_prop(1) = epsilon(r_R_prop(1))
         end if

      end subroutine check_data

!*****************************************************************************************

!*****************************************************************************************
!>
!     Compute surface radius.

      subroutine compute_r(y, z, r, r_R)

         use mod_common

         implicit none

         ! Input.
         real(kind=mk), intent(in) :: y
         real(kind=mk), intent(in) :: z

         ! Output.
         real(kind=mk), intent(out) :: r
         real(kind=mk), intent(out) :: r_R

         ! Compute surface radius (dimensional and dimensionless).
         r = sqrt(y**2+z**2)
         r_R = r/radius

      end subroutine compute_r

!*****************************************************************************************

!*****************************************************************************************
!>
!     Compute circulation for surface point.

      subroutine surface_circulation(r_R, circ_surf)

         use mod_common
         use bspline_oo_module
         use bspline_sub_module

         implicit none

         ! Input.
         real(kind=mk), intent(in) :: r_R

         ! Output.
         real(kind=mk), intent(out) :: circ_surf

         ! Local.
         integer :: iflag
         type(bspline_1d) :: spline_circ

         ! Initialize B-Spline representations for circulation.
         call spline_circ%initialize(r_R_prop(:), circ_prop(:), bspline_order_cubic, &
                                     iflag, .false.)
         if (iflag /= 0) then
            print *, 'error_1: ' // spline_circ%status_message(iflag)
            error stop
         end if

         ! Evaluate B-Spline representations for dimensionless surface radius.
         if (r_R < (1.0_mk-epsilon(r_R))) then
            call spline_circ%evaluate(r_R, 0, circ_surf, iflag)
            if (iflag /= 0) then
               print *, 'error_2: ' // spline_circ%status_message(iflag)
               error stop
            end if
         else
            circ_surf = 0.0_mk
         end if

      end subroutine surface_circulation

!*****************************************************************************************

!*****************************************************************************************
!>
!     Compute propeller radius with dimension.

      subroutine radius_dimension(r_prop_dim)

         use mod_common

         implicit none

         ! Output.
         real(kind=mk), dimension(:), allocatable, intent(out) :: r_prop_dim

         ! Local.
         integer :: i

         ! Allocate array.
         allocate(r_prop_dim(size(r_R_prop)))

         ! Compute dimensional propeller radius.
         do i=1, size(r_R_prop)
            r_prop_dim(i) = r_R_prop(i)*radius
         end do

      end subroutine radius_dimension

!*****************************************************************************************

!*****************************************************************************************
!>
!    Computing associated Legendre function and its derivative.

      subroutine compute_q(x, r, r_prop_dim, qf_radial, qfder_axial)

         use mod_common

         implicit none

         ! Input.
         real(kind=mk), intent(in) :: r, x
         real(kind=mk), dimension(:), intent(in) :: r_prop_dim

         ! Output
         real(kind=mk), dimension(:), allocatable, intent(out) :: qf_radial
         real(kind=mk), dimension(:), allocatable, intent(out) :: qfder_axial

         ! Local.
         integer :: j
         real(kind=mk), dimension(:), allocatable :: zeta
         real(kind=mk), dimension(:), allocatable :: dummy

         ! Allocate array.
         allocate(zeta(size(r_prop_dim)))
         allocate(dummy(size(r_prop_dim)))
         allocate(qf_radial(size(r_prop_dim)))
         allocate(qfder_axial(size(r_prop_dim)))

         ! Compute associated Legendre function and its derivative.
         do j=1, size(r_prop_dim)
            zeta(j) = (x**2+r**2+r_prop_dim(j)**2)/(2.0_mk*r*r_prop_dim(j))
            call qfun(0, zeta(j), dummy(j), qfder_axial(j))
            call qfun(1, zeta(j), qf_radial(j), dummy(j))
         end do

         ! Deallocate array.
         deallocate(zeta)
         deallocate(dummy)

      end subroutine compute_q

!*****************************************************************************************

!*****************************************************************************************
!>
!     This subroutine calculates the associated Legendre function (q-function) of the
!     second kind of degree (n-1/2) and zero order and its derivative by elliptic
!     integrals and recursion formulas. For large arguments a series expansion is used.
!     Maximum 100 elements are used in the series.
!
!     Input:
!
!     n           degree of the associated Legendre function (n-1/2)
!     x           argument of the associated Legendre function
!
!     Output:
!
!     qf          Associated Legendre function
!     qfder       First derivative of the associated Legendre function

      subroutine qfun(n, x, qf, qfder)

         use mod_common

         implicit none

         ! Input.
         integer, intent(in) :: n
         real(kind=mk), intent(in) :: x

         ! Output.
         real(kind=mk), intent(out) :: qf
         real(kind=mk), intent(out) :: qfder

         ! Local.
         integer :: ix, n1, i, j
         integer, parameter :: m = 100
         real(kind=mk) :: xmax, x2, x0, x1, a, xn, xi
         real(kind=mk) ::  qder, q0, q1, qder0, qder1, q, qfdr

         x0=x
         ix=0
         n1=n

         xmax=100
         if (n > 2) xmax=11.0_mk/(real(n-2, mk)**1.5)+1.0_mk
         if (x0 > xmax) goto 200

         x1=sqrt(2.0_mk/(x0+1.0_mk))
         x2=(x0-1.0_mk)/(x0+1.0_mk)

         q=(((.01451196212_mk*x2+.03742563713_mk)*x2+.03590092383_mk)*x2 + &
           .09666344259_mk)*x2+1.38629436112_mk
         a=(((.00441787012_mk*x2+.03328355346_mk)*x2+.06880248576_mk)*x2 + &
           .12498593597_mk)*x2+.5_mk
         q=q-a*log(x2)
         qder=(((.01736506451_mk*x2+.04757383546_mk)*x2+.06260601220_mk)*x2 + &
              .44325141463_mk)*x2+1.0_mk
         a=(((.00526449639_mk*x2+.04069697526_mk)*x2+.09200180037_mk)*x2 + &
           .24998368310_mk)*x2
         qder=qder-a*log(x2)

         q=q*x1
         qder=-qder*x1/(2.0_mk*x0-2.0_mk)
         if (n == 0) goto 101

         q0=x0*q+2.0_mk*(x0**2-1.0_mk)*qder
         q1=q
         q=q0
         qder0=.5_mk*(x0*q0-q1)/(x0**2-1.0_mk)
         qder1=qder
         qder=qder0
         if (n == 1) goto 101

         n1=n1-1
         do 100 i=1,n1
         xi=real(i, mk)
         q0=q
         qder0=qder
         q=2.0_mk*xi*x0*q/(xi+.5_mk)-(xi-.5_mk)*q1/(xi+.5_mk)
         qder=2.0_mk*xi*x0*qder/(xi-.5_mk)-(xi+.5_mk)*qder1/(xi-.5_mk)
         q1=q0
  100    qder1=qder0

  101    qf=q
         qfder=qder
         if (qf < 1.D-20) qf=0.0_mk
         if (qf < 1.D-20) qfdr=0.0_mk
         return

  200    x1=x0+1.0_mk
         xn=real(n1, mk)
         a=sqrt(2.0_mk/x1)
         if (n1 == 0) goto 203

         do 201 j=1,n1
         xi=real(j, mk)
         if (a < 1.D-70) a=0.0_mk
  201    a=a*.25_mk*(2.0_mk*xi-1._mk)/xi/x1

  203    q1=a
         j=0
  202    j=j+1
         xi=real(j, mk)
         a=a*(xn+xi-.5_mk)**2/xi/(xn+.5_mk*xi)/x1
         q1=q1+a
         if (a > 1.0e-50_mk .and. j < m) goto 202
         q1=q1*1.5707963267949_mk

         if (ix == 1) goto 20
         q=q1
         n1=n-1
         if (n == 0) n1=1
         ix=1
         goto 200

   20    qder=(x0*q-q1)*(real(n, mk)-.5_mk)/(x0**2-1.0_mk)
         goto 101

      end subroutine qfun

!*****************************************************************************************

!*****************************************************************************************
!>
!     Heaviside step function.
!
!     Reference:
!
!     Breslin, John P., and Poul Andersen,
!     Hydrodynamics of Ship Propellers.
!     Vol. 3,
!     Cambridge University Press, 1996,
!     Page 505,
!     Equation M2.6.

      function heaviside(x)

         use mod_common

         implicit none

         ! Local.
         real(kind=mk) :: heaviside, x

         ! Heaviside step function.
         heaviside = 0.0_mk
         if (x  > epsilon(x)) heaviside = 1.0_mk
         if (abs(x) <= epsilon(x)) heaviside = 0.5_mk

      end function heaviside

!*****************************************************************************************

!*****************************************************************************************
!>
!     Induced axial velocity (Actuator disc).
!
!     Reference:
!
!     Breslin, John P., and Poul Andersen,
!     Hydrodynamics of Ship Propellers.
!     Vol. 3,
!     Cambridge University Press, 1996,
!     Page 189,
!     Equation 9.93.

      subroutine induced_axial(x, r, r_prop_dim, qfder_axial, circ_surf, u_x)

         use mod_common
         use bspline_oo_module
         use bspline_sub_module

         implicit none

         ! Input.
         real(kind=mk), intent(in) :: x, r
         real(kind=mk), intent(in) :: circ_surf
         real(kind=mk), dimension(:), intent(in) :: qfder_axial
         real(kind=mk), dimension(:), intent(in) :: r_prop_dim

         ! Output.
         real(kind=mk), intent(out) :: u_x

         ! Local.
         integer :: j, iflag
         real(kind=mk) :: int_axial, a
         type(bspline_1d) :: int_spline_axial
         real(kind=mk), dimension(:), allocatable :: int_var_axial

         ! Allocate array.
         allocate(int_var_axial(size(r_prop_dim)))

         ! Induced axial velocity.
         do j=1, size(r_prop_dim)
            int_var_axial(j) = circ_prop(j)*(1.0_mk/sqrt(r_prop_dim(j))*qfder_axial(j))
         end do

         ! Initialize B-Spline representations for the integrand.
         call int_spline_axial%initialize(r_prop_dim(:), int_var_axial(:), &
                                          bspline_order_cubic, iflag, .false.)
         if (iflag /= 0) then
            print *,  'error_3 : ' // int_spline_axial%status_message(iflag)
            error stop
         end if

         ! Evaluate integral.
         call int_spline_axial%integral(r_prop_dim(1), radius, int_axial, iflag)
         if (iflag /= 0) then
            print *,  'error_4: ' // int_spline_axial%status_message(iflag)
            error stop
         end if

         ! Induced axial velocity on surface coordinates.
         a = (x/(4.0_mk*pi**2*r*sqrt(r))*omega/v_ship)
         u_x = blade_number*(a*int_axial-(1.0_mk-heaviside(x))* &
                   circ_surf*omega/(2.0_mk*pi*v_ship))

         deallocate(int_var_axial)

      end subroutine induced_axial

!*****************************************************************************************

!*****************************************************************************************
!>
!     Induced radial velocity (Actuator disc).
!
!     Reference:
!
!     Breslin, John P., and Poul Andersen,
!     Hydrodynamics of Ship Propellers.
!     Vol. 3,
!     Cambridge University Press, 1996,
!     Page 188,
!     Equation 9.85.

      subroutine induced_radial(r, r_prop_dim, qf_radial, u_r)

         use mod_common
         use bspline_oo_module
         use bspline_sub_module

         implicit none

         ! Input.
         real(kind=mk), intent(in) :: r
         real(kind=mk), dimension(:), intent(in) :: r_prop_dim
         real(kind=mk), dimension(:), intent(in) :: qf_radial

         ! Output
         real(kind=mk), intent(out) :: u_r

         ! Local.
         integer :: j, iflag
         real(kind=mk) :: int_radial
         type(bspline_1d) :: int_spline_radial
         type(bspline_1d) :: int_spline_der_radial
         real(kind=mk), dimension(:), allocatable :: funct_der
         real(kind=mk), dimension(:), allocatable :: deriv_var
         real(kind=mk), dimension(:), allocatable :: int_var_radial

         ! Allocate array.
         allocate(deriv_var(size(r_prop_dim)))
         allocate(funct_der(size(r_prop_dim)))
         allocate(int_var_radial(size(r_prop_dim)))

         ! Function to be derived.
         funct_der = circ_prop/(2.0_mk*pi)

         ! Initialize B-Spline representations for the derivative.
         call int_spline_der_radial%initialize(r_prop_dim(:), funct_der(:), &
                                               bspline_order_cubic, iflag, .false.)
         if (iflag /= 0) then
            print *,  'error_5 : ' // int_spline_der_radial%status_message(iflag)
            error stop
         end if

         ! Induced radial velocity.
         do j=1, size(r_prop_dim)
            ! Evaluate the derivative.
            call int_spline_der_radial%evaluate(r_prop_dim(j), 1, deriv_var(j), iflag)
            if (iflag /= 0) then
               print *, 'error_6: ' // int_spline_der_radial%status_message(iflag)
               error stop
            end if
            int_var_radial(j) = (r_prop_dim(j))*(deriv_var(j))* &
                                (1.0_mk/(sqrt(r_prop_dim(j)*r))*qf_radial(j))
         end do

         ! Initialize B-Spline representations for the integrand.
         call int_spline_radial%initialize(r_prop_dim(:), int_var_radial(:), &
                                           bspline_order_cubic, iflag, .false.)
         if (iflag /= 0) then
            print *,  'error_7 : ' // int_spline_radial%status_message(iflag)
            error stop
         end if

         ! Evaluate integral.
         call int_spline_radial%integral(r_prop_dim(1), radius, int_radial, iflag)
         if (iflag /= 0) then
            print *,  'error_8: ' // int_spline_radial%status_message(iflag)
            error stop
         end if
         u_r = blade_number*(omega/v_ship)*(1.0_mk/(2.0_mk*pi))*int_radial

        deallocate(deriv_var)
        deallocate(funct_der)
        deallocate(int_var_radial)

      end subroutine induced_radial

!*****************************************************************************************

!*****************************************************************************************
!>
!     Induced tangential velocity (Actuator disc).
!
!     Reference:
!
!     Breslin, John P., and Poul Andersen,
!     Hydrodynamics of Ship Propellers.
!     Vol. 3,
!     Cambridge University Press, 1996,
!     Page 172,
!     Equation 9.30.

      subroutine induced_tangential(x, r, circ_surf, u_t)

         use mod_common

         implicit none

         ! Input.
         real(kind=mk), intent(in) :: x,r, circ_surf

         ! Output.
         real(kind=mk), intent(out) :: u_t

         if (x < -epsilon(x)) then
            u_t = blade_number*circ_surf/(2.0_mk*pi*r)
         else if (abs(x) <= epsilon(x)) then
            u_t = blade_number*circ_surf/(4.0_mk*pi*r)
         else
            u_t = 0.0_mk
         end if

      end subroutine induced_tangential

!*****************************************************************************************

!*****************************************************************************************
!>
!     Compute y and z velocities.

      subroutine cartesian_velocity(y, z, u_r, u_t, u_y, u_z)

         use mod_common

         implicit none

         ! Input.
         real(kind=mk), intent(in) :: y, z, u_r, u_t

         ! Output.
         real(kind=mk), intent(out) :: u_y, u_z

         ! Local.
         real(kind=mk) :: theta

         theta = atan2(z,y)

         u_y = u_r*cos(theta) - u_t*sin(theta)
         u_z = u_t*cos(theta) + u_r*sin(theta)

      end subroutine cartesian_velocity

!*****************************************************************************************

!*****************************************************************************************
!>
!     Translate coordinates.

      subroutine move_coor(x, y, z, xx, yy, zz)

         use mod_common

         implicit none

         ! Input.
         real(kind=mk), intent(in) :: x, y, z

         ! Output.
         real(kind=mk), intent(out) :: xx, yy, zz

         xx = x - x_prop
         yy = y - y_prop
         zz = z - z_prop

      end subroutine move_coor

!*****************************************************************************************

!*****************************************************************************************

   end module mod_subroutines
   
!*****************************************************************************************
!> author: Saettone Simone
!  license: Technical University of Denmark
!  date: April 2018

!*****************************************************************************************

!*****************************************************************************************
!>
!   This subroutine calculates the velocities induced by the actuator disc.
!   The actuator disk is described is a Cartesian coordinate system which rotates with it.
!   The x-axis is positive towards the bow, the z-axis is positive to the starboard and
!   the y-axis completes the right-hand coordinate system. The origin of the coordinate
!   system is at the center of the actuator disk.
!
!   Input:
!   x      x-coordinate of the point where the induced velocity is computed
!   y      y-coordinate of the point where the induced velocity is computed
!   z      z-coordinate of the point where the induced velocity is computed
!
!   Output:
!   u_x    x-component of the induced velocity
!   u_y    y-component of the induced velocity
!   u_z    z-component of the induced velocity

   subroutine actvels(x, y, z, u_x, u_y, u_z) bind(c)

      use mod_common
      use mod_subroutines

      implicit none

      ! Input.
      real(kind=mk), intent(in) :: x, y, z

      ! Output.
      real(kind=mk), intent(out) :: u_x, u_y, u_z

      ! Local.
      real(kind=mk):: xx, yy, zz
      real(kind=mk) :: r, r_R, circ_surf,u_r, u_t
      real(kind=mk), dimension(:), allocatable :: r_prop_dim
      real(kind=mk), dimension(:), allocatable :: qf_radial
      real(kind=mk), dimension(:), allocatable :: qfder_axial

      ! Translate coordinates.
      call move_coor(x, y, z, xx, yy, zz)
      ! Check and modify input data.
      call check_data
      ! Compute surface radius.
      call compute_r(yy, zz, r, r_R)
      ! Compute circulation for surface point.
      call surface_circulation(r_R, circ_surf)
      ! Compute propeller radius with dimension.
      call radius_dimension(r_prop_dim)
      ! Computing associated Legendre function and its derivative.
      call compute_q(xx, r, r_prop_dim, qf_radial, qfder_axial)
      ! Induced axial velocity.
      call induced_axial(xx, r, r_prop_dim, qfder_axial, circ_surf, u_x)
      ! Induced radial velocity.
      call induced_radial(r, r_prop_dim, qf_radial, u_r)
      ! Induced tangential velocity.
      call induced_tangential(xx, r, circ_surf, u_t)
      ! Induced tangential velocity.
      call cartesian_velocity(yy, zz, u_r, u_t, u_y, u_z)

      deallocate(r_prop_dim)
      deallocate(qf_radial)
      deallocate(qfder_axial)

!*****************************************************************************************

!*****************************************************************************************

   end subroutine actvels
