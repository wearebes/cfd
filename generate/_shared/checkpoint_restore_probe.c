#if CHECKPOINT_TREE
# include "grid/quadtree.h"
#else
# include "grid/multigrid.h"
#endif
#include "utils.h"

scalar f[], d[];
vector u[];

int main (int argc, char ** argv)
{
  if (argc != 2) {
    fprintf (stderr, "usage: checkpoint_restore_probe CHECKPOINT.dump\n");
    return 2;
  }
  FILE * header_fp = fopen (argv[1], "r");
  if (!header_fp) {
    perror (argv[1]);
    return 3;
  }
  struct DumpHeader header = {0};
  if (fread (&header, sizeof(struct DumpHeader), 1, header_fp) != 1) {
    fprintf (stderr, "dump header read failed: %s\n", argv[1]);
    return 3;
  }
  fclose (header_fp);
  if (!restore (file = argv[1])) {
    fprintf (stderr, "restore failed: %s\n", argv[1]);
    return 3;
  }
  int interface_cells = 0, leaf_cells = 0;
  foreach (reduction(+:interface_cells) reduction(+:leaf_cells)) {
    leaf_cells++;
    if (f[] > 1e-12 && f[] < 1. - 1e-12)
      interface_cells++;
  }
  if (interface_cells <= 0 || leaf_cells <= 0) {
    fprintf (stderr, "restored field validation failed: %s\n", argv[1]);
    return 4;
  }
  if (fabs (t - header.t) > 1e-14) {
    fprintf (stderr, "restored time mismatch: %s\n", argv[1]);
    return 5;
  }
  printf ("%.17g,%d,%d,%d,%g,%g,%g,%g\n", t, header.i, depth(), leaf_cells,
          L0, X0, Y0, (double) interface_cells);
  return 0;
}
