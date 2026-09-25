/** Real downloaded photo slugs (Section 7.2), grouped by the plan's 8 search terms. Generated
 * from frontend/public/images/manifest.json -- see docs/CREDITS.md for photographer credit. */
export const IMAGES = {
  carServiceTechnician: [
    "car-service-technician-uzuzvjevkni",
    "car-service-technician-begtsocnhro",
    "car-service-technician-2k_-pg95qli",
    "car-service-technician-jl9zfztvswy",
  ],
  modernDealershipShowroom: [
    "modern-car-dealership-showroom-rvedgp-dkyy",
    "modern-car-dealership-showroom-bc5nnbwuob0",
    "modern-car-dealership-showroom-71lh24ybhxo",
    "modern-car-dealership-showroom-fxaruvd6oio",
  ],
  mechanicTabletDiagnostics: [
    "mechanic-tablet-diagnostics-seu9can7qla",
    "mechanic-tablet-diagnostics-g5nquyyjmea",
    "mechanic-tablet-diagnostics-heelt_9ydiu",
    "mechanic-tablet-diagnostics-o3ytqgi6fee",
  ],
  tireChangeWorkshop: [
    "tire-change-workshop-9uhal2dd9ae",
    "tire-change-workshop-csyanzll_ra",
    "tire-change-workshop-khf58h0htbc",
    "tire-change-workshop-rraapbvfska",
  ],
  customerHandingKeys: [
    "customer-handing-keys-idssolqfa8w",
    "customer-handing-keys-ctek-dlbkk4",
    "customer-handing-keys-ebpfjy7tyhe",
    "customer-handing-keys-aboff2gxb_0",
  ],
  evCharging: [
    "electric-vehicle-charging-xjlshl0hiik",
    "electric-vehicle-charging-xfayasmv1p8",
    "electric-vehicle-charging-2jrnvr0ac7s",
    "electric-vehicle-charging-n2td7kpivyc",
  ],
  brakeRepairCloseUp: [
    "brake-repair-close-up-al01ad0f_ki",
    "brake-repair-close-up-ii4xeyjem_i",
    "brake-repair-close-up-yqsgl2wkeha",
    "brake-repair-close-up-fwntoncjeb0",
  ],
  serviceAdvisorDesk: [
    "service-advisor-desk-3hp6_d9hxfy",
    "service-advisor-desk-n4ak7vy1mcm",
    "service-advisor-desk-5mk7vv6dhlg",
    "service-advisor-desk-6d3rldynbmm",
  ],
} as const;

const ALL_SERVICE_IMAGES = [
  ...IMAGES.carServiceTechnician,
  ...IMAGES.tireChangeWorkshop,
  ...IMAGES.brakeRepairCloseUp,
  ...IMAGES.mechanicTabletDiagnostics,
];

/** Deterministic pick so the same service always gets the same image across renders/pages. */
export function imageForService(code: string): string {
  let hash = 0;
  for (let i = 0; i < code.length; i++) hash = (hash * 31 + code.charCodeAt(i)) >>> 0;
  return ALL_SERVICE_IMAGES[hash % ALL_SERVICE_IMAGES.length];
}
