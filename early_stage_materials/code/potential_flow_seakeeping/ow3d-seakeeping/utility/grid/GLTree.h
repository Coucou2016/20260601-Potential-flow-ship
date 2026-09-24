#ifndef __GLTREE_H__
#define __GLTREE_H__

// Author: Luigi Giaccari
// giaccariluigi@msn.com

class GLTREE
{
private:
  int N; // number of points
  int *Leaves;
  int *LeavesFinder1;
  int *LeavesFinder2;
  double Toll;
  double Minx, Miny, PX, PY; // Sistema di riferimento
  int nxint, nyint;
  int *RangeStore;

public:
  GLTREE(double *, double *, int); // constructor
  ~GLTREE();                       // destructor

  // funzioni membro
  void SearchClosest(double *px, double *py, double *pk, int *idc, double *mindist);
  int *SearchRadius(double *px, double *py, double *pk, double r, int *n); // aggiunto il raggio e il numero di punti trovati nel raggio
  void SearchKClosest(double *px, double *py, double *pk, int k, int *idck, double *distances);
};

#endif