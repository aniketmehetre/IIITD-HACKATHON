export type InputType = 'url' | 'message' | 'qr';

export type CaseStatus = 
  | 'queued' 
  | 'processing' 
  | 'completed' 
  | 'failed';

export type PipelineStage = 
  | 'intake' 
  | 'triage' 
  | 'detonate' 
  | 'enrich' 
  | 'cluster' 
  | 'act' 
  | 'complete';

export interface StageEvent {
  id: string;
  stage: PipelineStage;
  message: string;
  timestamp: string;
  level: 'info' | 'warning' | 'error' | 'success';
  metadata?: Record<string, any>;
}

export interface PayeeDetails {
  upi_vpa?: string;
  psp_name?: string;
  bank_account?: string;
  ifsc?: string;
  wallet_address?: string | null;
}

export interface TriageDetails {
  domain: string;
  domain_age_days: number;
  registrar: string;
  claimed_brand: string;
  brand_match: boolean;
  known_campaign: boolean;
  should_detonate: boolean;
  risk_score: number; // 0-100
  verdict: 'HIGH_RISK' | 'LOW_RISK' | 'SUSPICIOUS';
  reasons: string[];
}

export interface DetonationStep {
  step_number: number;
  timestamp_offset: string;
  action: string;
  target_element: string;
  dummy_value_used?: string;
  screenshot_url?: string;
  telemetry: string;
}

export interface DetonationDetails {
  target_url: string;
  redirect_chain: string[];
  final_url: string;
  steps: DetonationStep[];
  extracted_payee: PayeeDetails;
  qr_payload?: string;
  synthetic_persona: {
    ip_proxy: string;
    user_agent: string;
    geo: string;
    device: string;
  };
  halt_reason: string;
}

export interface EnrichmentDetails {
  resolved_psp: string;
  bank_name: string;
  qr_decoded_uri?: string;
  wallet_chain?: string | null;
  wallet_balance_hint?: string | null;
}

export interface GraphNode {
  data: {
    id: string;
    label: string;
    type: 'domain' | 'payee' | 'case' | 'phone' | 'ip';
    risk_level?: 'critical' | 'high' | 'medium' | 'info';
    metadata?: Record<string, any>;
  };
}

export interface GraphEdge {
  data: {
    id: string;
    source: string;
    target: string;
    relationship: 'funnel_destination' | 'investigated_url' | 'shared_mule' | 'dns_host';
  };
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  total_clusters: number;
  total_cases_linked: number;
  disruption_metrics?: {
    domains_neutralized: number;
    estimated_protected_inr: number;
    active_mules_flagged: number;
  };
}

export interface ReportDrafts {
  i4c_complaint: string;
  bank_alert: {
    target_bank: string;
    risk_rating: string;
    recommended_action: string;
    account_number: string;
    vpa: string;
  };
  cert_in_advisory: {
    incident_type: string;
    malicious_fqdn: string;
    takedown_action: string;
  };
}

export interface CaseResult {
  case_id: string;
  payee: PayeeDetails;
  attribution: 'confirmed' | 'probable' | 'benign';
  triage: TriageDetails;
  detonation: DetonationDetails;
  enrichment: EnrichmentDetails;
  cluster: {
    cluster_id: string;
    size: number;
    shared_identifiers: string[];
  };
  evidence_hash: string;
  drafts: ReportDrafts;
  approved?: boolean;
  approved_at?: string;
}

export interface CaseSummary {
  id: string;
  type: InputType;
  target: string;
  status: CaseStatus;
  current_stage: PipelineStage;
  progress_percentage: number;
  created_at: string;
  updated_at: string;
  events: StageEvent[];
  result?: CaseResult;
}
