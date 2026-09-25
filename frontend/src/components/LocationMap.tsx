import { MapContainer, TileLayer, Marker, Popup } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { LocationOut } from "../lib/api";

// Vite bundles leaflet's marker images with hashed filenames, which breaks the library's
// default icon path lookup; point it at the CDN copies instead (standard workaround).
const markerIcon = new L.Icon({
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
});

export default function LocationMap({ locations }: { locations: LocationOut[] }) {
  const withCoords = locations.filter((l) => l.latitude != null && l.longitude != null);
  if (withCoords.length === 0) {
    return <div className="flex h-96 items-center justify-center rounded-[var(--radius-card)] bg-slate-100 text-slate-400">Map unavailable</div>;
  }
  const center: [number, number] = [withCoords[0].latitude as number, withCoords[0].longitude as number];

  return (
    <MapContainer center={center} zoom={9} scrollWheelZoom={false} className="h-96 w-full" aria-label="Meridian Auto Group locations map">
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {withCoords.map((loc) => (
        <Marker key={loc.location_id} position={[loc.latitude as number, loc.longitude as number]} icon={markerIcon}>
          <Popup>
            <strong>{loc.name}</strong>
            <br />
            {loc.address}, {loc.city}, {loc.state} {loc.zip}
            <br />
            {loc.phone}
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  );
}
