import { useEffect, useState } from "react";

// Resolve a server-streamed promise into client state; a superseded promise
// cannot clobber a newer one.
export function useResolved<T>(promise: Promise<T>, initial: T): T {
  const [value, setValue] = useState<T>(initial);
  useEffect(() => {
    let active = true;
    promise.then((resolved) => {
      if (active) setValue(resolved);
    });
    return () => {
      active = false;
    };
  }, [promise]);
  return value;
}
