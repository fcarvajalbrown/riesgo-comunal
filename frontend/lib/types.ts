export type Level = "SIN_DATOS" | "INFORMATIVO" | "BAJO" | "MODERADO" | "ALTO" | "CRITICO";
export type DataClass = "official" | "observed" | "forecast" | "official_warning" | "historical" | "municipal" | "derived" | "estimated" | "modelled";

export interface Evidence {
  label: string;
  value: string | number;
  data_class: DataClass;
  data_class_label: string;
  source: string;
  updated_at: string | null;
  provenance_id: number | null;
  note: string | null;
}

export interface ExposureItem {
  id: number;
  name: string | null;
  category?: string | null;
  lon: number;
  lat: number;
  is_demo?: boolean;
  enrollment?: string | null;
}

export interface Exposure {
  category: string;
  label: string;
  count: number;
  data_class: DataClass;
  data_class_label: string;
  source: string;
  items: ExposureItem[];
}

export interface Assessment {
  hazard: string;
  hazard_name: string;
  level: Level;
  level_label: string;
  headline: string;
  explanation: string[];
  evidence: Evidence[];
  exposure: Exposure[];
  missing: string[];
  actions: string[];
  thresholds: Record<string, number | string>;
  area_name: string | null;
  data_class: "derived";
  data_class_label: string;
  notice: string;
  uses_demo_data: boolean;
}

export interface Alert {
  id: number;
  issuer: string;
  hazard: string;
  level: string;
  title: string;
  description: string | null;
  source_url: string;
  starts_at: string;
  ends_at: string | null;
  created_at: string;
  entered_by_name?: string;
  automatic?: boolean;
  source_key?: string | null;
  provenance_id?: number | null;
  properties?: { event?: string; zones?: string[]; severity?: string } | null;
}

export interface ComunaAssessment {
  municipality: { id: number; name: string; cut_code: string };
  computed_at: string;
  overall_level: Level;
  overall_level_label: string;
  notice: string;
  assessments: Assessment[];
}

export interface AhoraResponse extends ComunaAssessment {
  alerts: Alert[];
  alert_feed_note: string;
  exposure_summary: { hazard: string; hazard_name: string; level: Level; level_label: string; exposure: { label: string; count: number; data_class: DataClass }[] }[];
}

export interface SectorResult {
  id: number;
  name: string;
  kind: "municipal" | "analysis_cell";
  is_demo: boolean;
  levels: Record<string, Level>;
  overall_level: Level;
  overall_level_label: string;
  reasons: string[];
  uses_demo_data: boolean;
}

export interface RiesgoResponse extends ComunaAssessment {
  sectors: SectorResult[];
  sector_kind: "municipal" | "analysis_cell" | null;
}

export interface Trend {
  n: number;
  conclusion: string;
  statement: string;
  p_value: number | null;
}

export interface EarthquakeStats {
  key: string;
  title: string;
  period: string;
  sample_size: number;
  series: { year: number; total: number; m4: number; m5: number; m6: number; max_magnitude: number | null }[];
  source: string;
  updated_at: string | null;
  provenance_id: number | null;
  method: string;
  limitations: string[];
  trend: Trend;
}

export interface IncidentStats {
  key: string;
  title: string;
  empty?: boolean;
  message?: string;
  is_demo?: boolean;
  period?: string;
  sample_size: number;
  affected_people?: number;
  by_year?: { year: number; total: number }[];
  by_hazard?: { hazard: string; label: string; total: number; people: number }[];
  by_sector?: { sector: string; total: number; years_with_events: number }[];
  seasonality?: { month: number; label: string; total: number }[];
  recurrence?: { sector: string; total: number; years_with_events: number }[];
  method?: string;
  limitations?: string[];
  trend?: Trend;
}

export interface IcfsrContext {
  title: string;
  value: number;
  level: string;
  year: number;
  rank: number;
  total: number;
  components: Record<string, number>;
  source: string;
  updated_at: string | null;
  provenance_id: number | null;
  note: string;
}

export interface PlanificarResponse {
  icfsr: IcfsrContext | null;
  earthquakes: EarthquakeStats;
  incidents: IncidentStats;
  assessments: Assessment[];
  notice: string;
}

export interface Me {
  user: { id: number; email: string; name: string; role: string };
  permissions: string[];
  municipality: {
    id: number;
    name: string;
    cut_code: string;
    region: string | null;
    slug: string;
    lon: number;
    lat: number;
    bbox_geojson: { type: "Polygon"; coordinates: number[][][] } | null;
    config: {
      branding: { display_name: string | null; primary_color: string; logo_url: string | null };
      hazards: Record<string, { enabled: boolean; thresholds: Record<string, number | string> }>;
      terminology?: Record<string, string>;
    };
  };
  municipalities: { id: number; name: string; slug: string }[];
}

export interface LayerInfo {
  key: string;
  name: string;
  description: string;
  data_class: DataClass;
  geometry: string;
  legend: { value: string; label: string }[];
  default_on: boolean;
  source: string;
  updated_at: string | null;
  provenance_id: number | null;
}

export interface SourceRef {
  source: string;
  updated_at: string | null;
  data_class: DataClass | null;
  provenance_id: number | null;
}

export interface AssistantAnswer {
  answer: string;
  sources: SourceRef[];
  mode: string;
  tools: string[];
  generated_at: string;
  disclaimer: string;
  notice?: string;
}

export interface ReportItem {
  text: string;
  data_class: DataClass | null;
  data_class_label: string | null;
  source: string | null;
  updated_at: string | null;
}

export interface Report {
  role: string;
  title: string;
  municipality: string;
  generated_at_local: string;
  overall_level: Level;
  overall_level_label: string;
  sections: { title: string; items: ReportItem[] }[];
  sources: { source: string; updated_at_local: string | null }[];
  disclaimer: string;
}

export interface RasterInfo {
  id: number;
  name: string;
  is_demo: boolean;
  provenance_id: number | null;
  created_at: string;
  west: number;
  south: number;
  east: number;
  north: number;
  properties: { crs?: string; bands?: number; resolution?: number[]; min?: number; max?: number };
}
