module reference
implicit none
integer, parameter :: nofmax=512,nmumax=1
integer :: nfs=64,nmu=0,ngap=0,gap(1)=0
real :: zbot=1.e6,zwl=0.,g=9.80665,rho=1025.,pi=acos(-1.),wangl(1)=0.,waven
contains
subroutine stop1(message)
character(*) :: message
print *, message
stop 1
end subroutine stop1
function pq(dy,dz)  !pq=source (flux 2 pi) potential. dy,dz vector from source point to actual point
real:: pq,dy,dz
pq=0.5*log(dy**2+dz**2)
end function pq

function pqn(dy1,dz1,dy2,dz2)   !pqn=flux (area/time) between p1, p2 due to source of strength 2 pi.
real:: pqn,dy1,dz1,dy2,dz2             !pqn positive for flow to the left when looking from p1 to p2
pqn=-atan2(dy2*dz1-dz2*dy1,dy1*dy2+dz1*dz2)
end function pqn

function pqs(yof,zof,yq,zq,mp)                                           !=pq with y=0 mirror source
integer:: mp                                                 !and possibly with bottom mirror source
real:: pqs,yof,zof,yq,zq
pqs=pq(yof-yq,zof-zq)+mp*pq(yof+yq,zof-zq)    
if (zbot<1000.) pqs=pqs+pq(yof-yq,zof-(2*zbot-zq))+mp*pq(yof+yq,zof-(2*zbot-zq))
end function pqs

function pqsn(yof1,zof1,yof2,zof2,yq,zq,mp)                             !=pqn with y=0 mirror source
integer:: mp
real:: pqsn,yof1,zof1,yof2,zof2,yq,zq                       !and possibly with bottom mirror sources
pqsn=pqn(yof1-yq,zof1-zq,yof2-yq,zof2-zq)+mp*pqn(yof1+yq,zof1-zq,yof2+yq,zof2-zq)
if (zbot<1000.) pqsn=pqsn+pqn(yof1-yq,zof1-(2*zbot-zq),yof2-yq,zof2-(2*zbot-zq)) &
 +mp*pqn(yof1+yq,zof1-(2*zbot-zq),yof2+yq,zof2-(2*zbot-zq))  
end function pqsn

subroutine addedmassexcitations(nof1,yof1,zof1,om,ndof,addedm1,diff1,frkr1)
! added mass and wave excitation for deep and shallow water, symmetrical section
! bottom at zbot, surface at zwl. for deep water use zbot=1.e6. water density 1 assumed. 
! complex added mass = mass-i/omegae*damping for vertical (ndof=1; 1x1 matrix) or
! horizontal/roll motion (ndof=2; 2x2 matrix) as well as vertical (ndof=1) diffraction
! and Froude-Krilow forces or horizontal force and roll moment (ndof=2)
! section offset points from basis (y=0)to port wl point
! +y to starboard; +z downwards. last point should be on waterline
integer, intent(in):: nof1             !number of offsets on one half section
integer:: ndof                         !number of degrees of freedom: 1 heave, 2 sway/roll
integer:: mp                           !+1 if ndof=1; -1 if ndof=2
integer:: i,j                          !indices
integer:: iw                           !index of wave angle
integer:: is                           !points to row if equation solver detects singularity
integer:: l                            !motion index
integer:: m                            !force or degree-of-freedom index
integer:: k                            !index of offset points on section
integer:: nf                           !number of free-surface panels (undamped)
real:: om                              !circular frequency
real:: yof1(nofmax),zof1(nofmax)       !y and z coordinates of offset points of one section
real:: yq(0:nofmax),zq(0:nofmax)       !y and z coordinates of sources
real:: t                               !water depth
real:: fact1,fact2,factor,fact         !factors
real:: h                               !point distance on free surface near to body
real:: hend                            !point distance on free surface far from body
real:: dy,dz                           !range of contour segment in y and z direction
real:: sinw                            !sin(wave angle)
complex:: a(0:nofmax,0:nofmax+3+nmumax)!coefficient matrix for source strengths determination
complex:: ciom                         !i*om
complex:: detl                         !log(determinant) of a
complex:: f(2,2+nmumax)                !force amplitude
complex:: addedm1(ndof,ndof)           !complex added mass matrix
complex:: diff1(ndof,nmu)              !diffraction force amplitude, one section
complex:: frkr1(ndof,nmu)              !Froude-Krilow force amplitude, one section
complex:: zw1,zw2,zw1a,zw2a            !intermediate values

if (nof1.gt.50) call stop1('*** Too many points on section. should be <=50')
if (ndof.ne.1.and.ndof.ne.2) call stop1('*** Incorrect ndof. should be 1 or 2') 
if (nmu.gt.nmumax) call stop1('*** Too many angles')
if (nof1+nfs>nofmax) call stop1('*** Too many body + waterline panels')      
addedm1=0.
diff1=0.
twofreesurfacediscretisations: do nf=25,28,3                   !uses two values nf; results averaged
 mp=3-2*ndof
 ciom=(0.,1.)*om
 t=zbot-zwl                                                                           !t=water depth
 waven=max(om**2/g,om/sqrt(g*t))
 if (waven*t<6) then
  do i=1,10                               !for shallow water: iterative determination of wave number
   waven=waven-(waven*tanh(waven*t)-om**2/g)/(tanh(waven*t)+waven/cosh(waven*t)**2)/2
  enddo
  fact1=g*exp( waven*t)/2/cosh(waven*t); fact2=g*exp(-waven*t)/2/cosh(waven*t)
 else
  fact1=g; fact2=0.
 endif
 h=sqrt((yof1(nof1)-yof1(nof1-1))**2+(zof1(nof1)-zof1(nof1-1))**2)      !near distance on free surf.
 hend=2*pi/(12*waven)                      !far-off distance of points on free surface=wavelength/12

 !Compute free surface grid points yof1,zof1 and all source points yq,zq
 i=0
 BodySegments: do k=1,nof1-1
  if (ngap>0.and.any(gap(1:ngap)==k)) cycle
  i=i+1
  yq(i)=(yof1(k)+yof1(k+1))/2-(zof1(k+1)-zof1(k))/20                   !source points within section
  zq(i)=(zof1(k)+zof1(k+1))/2+(yof1(k+1)-yof1(k))/20
 enddo BodySegments

 FreeSurfaceSegments: do k=nof1,nof1+nfs-1
  h=min(h*1.5,hend)
  yof1(k+1)=yof1(k)-h
  zof1(k+1)=zwl
  yq(k-ngap)=yof1(k)-0.5*h
  zq(k-ngap)=zwl-1.0*h
 enddo FreeSurfaceSegments

 yq(0)=0
 zq(0)=zwl-abs(yof1(nof1+nfs))/2
 a(0:nof1-ngap+nfs-1,nof1-ngap+nfs:nof1-ngap+nfs-1+ndof+nmu)=0.             !inhomogeneous terms = 0
 frkr1(1:ndof,1:nmu)=0

 !Body boundary condition (panel integrals) and Fr.-Krilow forces
 j=0
 BodySegm:do k=1,nof1-1
  if (ngap>0.and.any(gap(1:ngap)==k)) cycle
  j=j+1
  dy=yof1(k+1)-yof1(k)
  dz=zof1(k+1)-zof1(k)
  if (mp.eq.1) then
  a(j,nof1-ngap+nfs)=+ciom*dy
  else
  a(j,nof1-ngap+nfs  )=-ciom*dz                                 !inhomogeneous terms for body motion
  a(j,nof1-ngap+nfs+1)=+ciom*(yof1(k+1)**2-yof1(k)**2+zof1(k+1)**2-zof1(k)**2)/2
  endif
  WaveAngles: do iw=1,nmu
   sinw=sin(wangl(iw)*pi/180)
   zw1=cmplx(-waven*dz,waven*sinw*dy)
   !print *,'om',om,waven,dz,zw1
   if (abs(zw1)>51) call stop1('Frequency too high')
   if (abs(zw1).lt.0.001) zw1=0.001                    ! stop 'frequency too low' seems unnecessary
   zw1a=-conjg(zw1)
   zw2 =exp(waven*cmplx(-zof1(k)+zwl,yof1(k)*sinw))* &
    merge((exp(zw1 )-1.)/zw1,1.+0.5*zw1,abs(zw1)>0.01)
   zw2a=exp(waven*cmplx( zof1(k)-zwl,yof1(k)*sinw))* &
    merge((exp(zw1a)-1.)/zw1a,1.+0.5*zw1a,abs(zw1a)>0.01)
   if (mp.eq.1) then                                                                   !heave motion
    a(j,nof1-ngap+nfs-1+ndof+iw)=-fact1*waven/om*real(cmplx(dy,sinw*dz)*zw2)*(0.,1.)
    frkr1(1,iw)=frkr1(1,iw)-fact1*2*real(zw2 )*dy*rho
    Shallow: if (fact2/=0) then
     a(j,nof1-ngap+nfs-1+ndof+iw)=a(j,nof1-ngap+nfs-1+ndof+iw) &
      +fact2*waven/om*real(cmplx(dy,-sinw*dz)*zw2a)*(0.,1.)
     frkr1(1,iw)=frkr1(1,iw)-fact2*2*real(zw2a)*dy*rho
    endif Shallow
   else                                                                            !sway/roll motion
    a(j,nof1-ngap+nfs-1+ndof+iw)=-fact1*waven/om*real(cmplx(-sinw*dz,dy)*zw2)
    frkr1(1,iw)=frkr1(1,iw)+fact1*(0.,2.)*aimag(zw2)*dz*rho
    frkr1(2,iw)=frkr1(2,iw)-fact1*(0.,1.)*aimag(zw2)* &
     (yof1(k+1)**2-yof1(k)**2+zof1(k+1)**2-zof1(k)**2)*rho
    ShallowWater: if (fact2/=0) then
    a(j,nof1-ngap+nfs-1+ndof+iw)=a(j,nof1-ngap+nfs-1+ndof+iw) &
     +fact2*waven/om*real(cmplx( sinw*dz,dy)*zw2a)  
    frkr1(1,iw)=frkr1(1,iw)+fact2*(0.,2.)*aimag(zw2a)*dz*rho 
    frkr1(2,iw)=frkr1(2,iw)-fact2*(0.,1.)*aimag(zw2a)*    &
     (yof1(k+1)**2-yof1(k)**2+zof1(k+1)**2-zof1(k)**2)*rho
    endif ShallowWater
   endif                                                                         !heave or sway/roll
  enddo WaveAngles
  Columns: do i=ndof-1,nof1-ngap+nfs-1
   a(j,i)=pqsn(yof1(k),zof1(k),yof1(k+1),zof1(k+1),yq(i),zq(i),mp)
  enddo Columns
 enddo BodySegm

  !Free-surface condition near to body
  FreeSSegmentsNear: do k=nof1,nof1+nf
   dy=yof1(k+1)-yof1(k)
  AllSources:do i=ndof-1,nof1-ngap+nfs-1            !2-point integration for correct integral at k=i
   a(k-ngap,i)=pqsn(yof1(k),zwl,yof1(k+1),zwl,yq(i),zq(i),mp) &
    +om**2/g*abs(dy)*(pqs(yof1(k)+0.316*dy,zwl,yq(i),zq(i),mp) &
    +pqs(yof1(k)+0.684*dy,zwl,yq(i),zq(i),mp))/2 
  enddo AllSources
 enddo FreeSSegmentsNear

 !Free-surface condition far from body (radiation condition)
 FarSegments: do k=nof1+nf+1,nof1+nfs-1
  dy=yof1(k+1)-yof1(k)
  factor=(real(k-nof1-nf)/(nfs-nf-1))**2
  AllColumns: do i=ndof-1,nof1-ngap+nfs-1
   a(k-ngap,i)=waven*abs(dy)*(pqs(yof1(k)+0.316*dy,zwl,yq(i),zq(i),mp) &
                             +pqs(yof1(k)+0.684*dy,zwl,yq(i),zq(i),mp))/2 &
    -(0.,1.)*(pqs(yof1(k+1)-factor*dy,zwl,yq(i),zq(i),mp) &
             -pqs(yof1(k  )-factor*dy,zwl,yq(i),zq(i),mp))
  enddo AllColumns
 enddo FarSegments

 if (ndof==1) a(0,0:nof1-ngap+nfs-1)=1.                      !sum of sources = 0 only in case ndof=1
 call simqcd(a(ndof-1,ndof-1),nof1-ngap+nfs+1-ndof,ndof+nmu,nofmax+1,is,1.e-5,detl) !solve equations
 if (is.ne.0) call stop1('***  Singular equation system. Coinciding offset points?') 

 Forces: do m=1,ndof                                             !ndof=1 heave, ndof=2 sway and roll
  MotionsAndWaves: do l=1,ndof+nmu                                    !m force index, l motion index
   f(m,l)=0
   AllBodySegments: do k=1,nof1-1                                             !k section point index
    if (ngap>0.and.any(gap(1:ngap)==k)) cycle
    dy=yof1(k+1)-yof1(k)
    dz=zof1(k+1)-zof1(k)
    if (mp.eq.1) then; fact=+dy                                                        !heave motion
    else
     if (m.eq.1) fact=-dz
     if (m.eq.2) fact=+0.5*(yof1(k+1)**2-yof1(k)**2+zof1(k+1)**2-zof1(k)**2)
    endif
    ForAllSources: do i=ndof-1,nof1-ngap+nfs-1
     f(m,l)=f(m,l)+a(i,nof1-ngap+nfs-1+l)*fact* &
      (pqs(yof1(k)+0.316*dy,zof1(k)+0.316*dz,yq(i),zq(i),mp)     &   
      +pqs(yof1(k)+0.684*dy,zof1(k)+0.684*dz,yq(i),zq(i),mp))/2
    enddo ForAllSources
   enddo AllBodySegments
   if (l<=ndof) then   
    addedm1(m,l)=addedm1(m,l)+ciom*f(m,l)/(-om**2)*rho
   else
    diff1(m,l-ndof)=diff1(m,l-ndof)-ciom*f(m,l)*rho
   endif          !/2 because of average for nf=25,28; *2 because of symmetry
  enddo MotionsAndWaves
 enddo Forces
enddo TwoFreeSurfaceDiscretisations
end subroutine addedmassexcitations

subroutine simqcd(a,n,nr,im,i,s,detl)
! Gauss algorithm for a complex linear equation system. Full matrix, several inhomogeneous vectors.
! a(row,column)=complex coefficient matrix + NEGATIVE right-hand sides as additional columns. When 
! finished right-hand sides are replaced by the solutions. Coefficient matrix is destroyed.
! n=no. of equations (rows), nr no. of right-hand sides, im range of first index of a.
! i=0 after normal solutions, /=0 if a pivot is <s (singular or near-singular matrix a).
! detl ist ln(determinant of coefficient matrix). With column pivoting.
real:: s
integer:: n,nr,im,i,j,k,nnr,mmr,k1,k2,imax
complex:: biga,save,detl,a(*)
nnr=(n+nr)*im
mmr=n*im
k1=-im
detl=0.
do i=1,n
 k1=k1+im+1
 biga=a(k1)
 imax=k1
 do j=k1+1,k1+n-i
  if (abs(biga).lt.abs(a(j))) then
  biga=a(j)
  imax=j
  endif
 enddo
 if (abs(biga).lt.s) return
 detl=detl+log(biga)
 a(imax)=a(k1)
 do k=k1+im,nnr,im
  imax=imax+im
  save=-a(imax)/biga
  a(imax)=a(k)
  a(k)=save
  k2=k1
  do j=k+1,k+n-i
   k2=k2+1
   a(j)=a(j)+a(k2)*save
  enddo
 enddo
enddo
do i=mmr,nnr-1,im
 k1=mmr+1
 do j=n,2,-1
  k1=k1-im
  k2=i
  save=a(i+j)
  do k=k1,k1+j-2
   k2=k2+1
   a(k2)=a(k2)+a(k)*save
  enddo
 enddo
enddo
i=0
end subroutine simqcd

end module reference
program verify
use reference
implicit none
integer :: n,i
real :: y(nofmax),z(nofmax),omega
complex :: am(1,1),df(1,0),fk(1,0)
read(*,*)n,omega
do i=1,n
read(*,*)y(i),z(i)
enddo
call addedmassexcitations(n,y,z,omega,1,am,df,fk)
write(*,'(2ES26.17)')real(am(1,1)),aimag(am(1,1))
end program verify
