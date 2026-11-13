export const BLOOD_GROUPS = ["O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-"] as const;
export type BloodGroup = (typeof BLOOD_GROUPS)[number];

export const COMPONENTS = ["whole_blood", "red_cells", "platelets", "plasma"] as const;
export type Component = (typeof COMPONENTS)[number];

export const COMPONENT_LABELS: Record<Component, string> = {
  whole_blood: "Whole blood",
  red_cells: "Red cells",
  platelets: "Platelets",
  plasma: "Plasma",
};

export const CONDITIONS = {
  accident: { label: "Accident / trauma", score: 100 },
  delivery_complication: { label: "Delivery complication", score: 100 },
  dengue_low_platelets: { label: "Dengue, low platelets", score: 80 },
  thalassemia: { label: "Thalassemia", score: 75 },
  cancer_treatment: { label: "Cancer treatment", score: 65 },
  planned_surgery: { label: "Planned surgery", score: 40 },
  other: { label: "Other", score: 20 },
} as const;
export type Condition = keyof typeof CONDITIONS;

export type LatLng = [number, number];
export type Role = "public" | "donor" | "hospital" | "bank_admin" | "admin";

export interface User {
  id: string;
  role: Role;
  name: string | null;
  phone: string | null;
  email: string | null;
  donor_id: string | null;
  bank_id: string | null;
  hospital_id: string | null;
}

export interface TokenResponse {
  token: string;
  user: User;
}

export interface City {
  id: string;
  name: string;
  center: LatLng;
  bbox: [number, number, number, number];
  notes?: string | null;
}

export interface Bank {
  id: string;
  name: string;
  area: string;
  city_id: string;
  lat: number;
  lng: number;
  phone: string;
  verified: boolean;
}

export interface BankHit {
  bank_id: string;
  name: string;
  area: string;
  lat: number;
  lng: number;
  phone: string;
  distance_km: number;
  est_travel_min: number;
  units: number;
  units_by_group: Record<string, number>;
}

export interface DonorHit {
  donor_id: string;
  name: string;
  blood_group: string;
  lat: number;
  lng: number;
  distance_km: number;
}

export interface TraceStep {
  node: string;
  lat: number;
  lng: number;
  dist_km: number;
  parent: string | null;
}

export interface BankReached {
  bank_id: string;
  node: string;
  lat: number;
  lng: number;
  dist_km: number;
  has_stock: boolean;
}

export interface SearchResult {
  city_id: string;
  group: string;
  component: string;
  radius_km: number;
  compatible_groups: string[];
  start: LatLng;
  banks: BankHit[];
  route: LatLng[];
  route_bank_id?: string;
  donors: DonorHit[];
  junctions_visited: number;
  trace?: TraceStep[];
  banks_reached?: BankReached[];
}

export interface Contact {
  donor_id: string;
  name: string;
  blood_group: string;
  phone: string;
  views_left_today: number;
}

export interface Donation {
  date: string;
  bank_id: string;
  bank_name: string | null;
  component: string;
  unit_id: string;
}

export interface Donor {
  id: string;
  name: string;
  age: number;
  gender: "M" | "F";
  blood_group: string;
  phone: string;
  lat: number;
  lng: number;
  linked_bank_id: string | null;
  linked_bank_name: string | null;
  last_donation_date: string | null;
  next_eligible_date: string | null;
  health_checklist: Record<string, boolean>;
  eligible: boolean;
  eligibility_reasons: string[];
  available: boolean;
  contact_consent: boolean;
  donations: Donation[];
}

export interface SuggestedBank extends Bank {
  distance_km: number;
}

export interface AllocatedUnit {
  unit_id: string;
  blood_group: string;
  expires_on: string;
}

export interface Allocation {
  bank_id: string;
  bank_name: string;
  distance_km: number;
  units: AllocatedUnit[];
  status: "pending" | "accepted" | "rejected";
  bank_phone?: string | null;
}

export interface BloodRequest {
  id: string;
  hospital_name: string;
  blood_group: string;
  component: Component;
  units_needed: number;
  units_allocated: number;
  patient_condition: Condition;
  base_score: number;
  priority: number;
  status: "queued" | "allocated" | "partial" | "unfulfilled" | "completed";
  created_at: string;
  allocations: Allocation[];
  donor_suggestions: { donor_id: string; name: string; blood_group: string; distance_km: number }[];
}

export interface StockRow {
  blood_group: string;
  component: Component;
  units: number;
  earliest_expiry: string;
  expiring_soon: number;
}

export interface Unit {
  id: string;
  blood_group: string;
  component: Component;
  expires_on: string;
  status: string;
}

export interface Stock {
  bank: Bank;
  today: string;
  total_units: number;
  rows: StockRow[];
  expiring_soon: Unit[];
}

export interface BankRequest {
  request_id: string;
  hospital_name: string;
  blood_group: string;
  component: Component;
  patient_condition: Condition;
  base_score: number;
  created_at: string;
  units: AllocatedUnit[];
  distance_km: number;
  status: "pending" | "accepted" | "rejected";
}

export interface Transaction {
  id: string;
  action: string;
  unit_ids: string[];
  at: string;
  details: Record<string, unknown>;
}

export interface Place extends Bank {
  kind: "hospital" | "bank";
}

export interface Report {
  id: string;
  donor_id: string;
  reporter_role: string;
  reason: string;
  status: string;
  at: string;
}
