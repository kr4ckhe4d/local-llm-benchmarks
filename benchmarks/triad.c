#include <stdio.h>
#include <stdlib.h>
#include <omp.h>
#define N (64UL*1024*1024)   /* 512 MiB per array, 3 arrays = 1.5 GiB, >> 96 MiB L3 */
int main(void){
  double *a=aligned_alloc(64,N*8),*b=aligned_alloc(64,N*8),*c=aligned_alloc(64,N*8);
  if(!a||!b||!c){fprintf(stderr,"alloc failed\n");return 1;}
  #pragma omp parallel for
  for(size_t i=0;i<N;i++){a[i]=1.0;b[i]=2.0;c[i]=3.0;}
  double best=0, scalar=3.0;
  for(int r=0;r<10;r++){
    double t0=omp_get_wtime();
    #pragma omp parallel for
    for(size_t i=0;i<N;i++) a[i]=b[i]+scalar*c[i];
    double dt=omp_get_wtime()-t0;
    double gbs=(3.0*N*8.0)/dt/1e9;
    if(gbs>best) best=gbs;
  }
  printf("Triad best: %.1f GB/s  (%d threads, %.0f MiB/array)\n",
         best, omp_get_max_threads(), N*8.0/1048576.0);
  if(a[0]!=b[0]+scalar*c[0]) printf("verify failed\n");
  return 0;
}
