/** Full-circle stationary bubble on [-1,1]^2.
 * Runner resolution selects h = 1/resolution and the same-numbered model.
 * The runner sets STATIONARY_LEVEL so internal N = 2*resolution.
 * Reuse all physics, providers, events and diagnostics from the quadrant host.
 */
#define STATIONARY_FULL_DOMAIN 1
#include "stationary-clsvof.c"
