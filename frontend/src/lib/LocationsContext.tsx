import { createContext, useContext, useEffect, useState } from "react";
import { listLocations, type LocationOut } from "./api";

interface LocationsState {
  locations: LocationOut[];
  loading: boolean;
  selectedId: number | null;
  setSelectedId: (id: number) => void;
  selected: LocationOut | null;
}

const LocationsContext = createContext<LocationsState>({
  locations: [], loading: true, selectedId: null, setSelectedId: () => {}, selected: null,
});

export function useLocations() {
  return useContext(LocationsContext);
}

export function LocationsProvider({ children }: { children: React.ReactNode }) {
  const [locations, setLocations] = useState<LocationOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  useEffect(() => {
    listLocations()
      .then((data) => {
        setLocations(data);
        if (data.length > 0) setSelectedId(data[0].location_id);
      })
      .catch(() => setLocations([]))
      .finally(() => setLoading(false));
  }, []);

  const selected = locations.find((l) => l.location_id === selectedId) ?? null;

  return (
    <LocationsContext.Provider value={{ locations, loading, selectedId, setSelectedId, selected }}>
      {children}
    </LocationsContext.Provider>
  );
}
