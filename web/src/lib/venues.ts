import venuesData from "@/lib/venues.json";

export interface Venue {
  city: string;
  stadium: string;
  country: string;
  altitudeM: number;
  roofed: boolean;
  lat: number;
  lon: number;
}

const venues = venuesData as Venue[];
const byCity = new Map(venues.map((venue) => [venue.city, venue]));

export function venueForCity(city: string): Venue | undefined {
  return byCity.get(city);
}

const LOAD_BEARING_ALTITUDE_M = 1000;

export function venueLine(city: string): string | null {
  const venue = byCity.get(city);
  if (!venue) return null;
  if (venue.altitudeM < LOAD_BEARING_ALTITUDE_M) return venue.stadium;
  return `${venue.stadium}, ${venue.altitudeM.toLocaleString("en-GB")} m`;
}
