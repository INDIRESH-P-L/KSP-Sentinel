import { Loading } from 'frontend';

export function Default() {
  return <Loading />;
}

export function CustomLabel() {
  return <Loading label="Initializing GIS basemap…" />;
}
