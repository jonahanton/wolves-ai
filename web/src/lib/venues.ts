export interface VenueTraits {
  roof: boolean;
  heat: boolean;
  altitude: boolean;
}

const NONE: VenueTraits = { roof: false, heat: false, altitude: false };

const VENUES: Record<string, Partial<VenueTraits>> = {
  Atlanta: { roof: true },
  Dallas: { roof: true, heat: true },
  Houston: { roof: true, heat: true },
  "Los Angeles": { roof: true },
  Vancouver: { roof: true },
  Miami: { heat: true },
  "Kansas City": { heat: true },
  Monterrey: { heat: true },
  "Mexico City": { altitude: true },
  Guadalajara: { altitude: true },
};

export function venueTraits(city: string): VenueTraits {
  return { ...NONE, ...VENUES[city] };
}
