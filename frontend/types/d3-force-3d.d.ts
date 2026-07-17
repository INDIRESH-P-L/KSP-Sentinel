// Minimal declaration for d3-force-3d (no official @types package).
// It mirrors d3-force's API with an added z dimension and an nDim argument to
// forceSimulation. We only type what NetworkView uses.
declare module "d3-force-3d" {
  export function forceSimulation(nodes?: any[], nDim?: number): any;
  export function forceManyBody(): any;
  export function forceLink(links?: any[]): any;
  export function forceCenter(x?: number, y?: number, z?: number): any;
  export function forceCollide(radius?: number | ((node: any) => number)): any;
  export function forceX(x?: number): any;
  export function forceY(y?: number): any;
  export function forceZ(z?: number): any;
}
