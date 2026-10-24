import { CaseSummary, GraphData } from './types';

export const MOCK_CASES: Record<string, CaseSummary> = {
  "c-pmcares-9281": {
    id: "c-pmcares-9281",
    type: "url",
    target: "https://pmcares-relief-claim.sbi-update.fake.in/kyc-verify",
    status: "completed",
    current_stage: "complete",
    progress_percentage: 100,
    created_at: "2026-10-24T18:10:02Z",
    updated_at: "2026-10-24T18:10:28Z",
    events: [
      {
        id: "evt-01",
        stage: "intake",
        message: "Target URL received via citizen telemetry feed. Ingestion validated.",
        timestamp: "18:10:02",
        level: "info"
      },
      {
        id: "evt-02",
        stage: "triage",
        message: "RDAP lookup: domain registered 2 days ago via NameCheap. Host: 103.21.58.12.",
        timestamp: "18:10:05",
        level: "warning",
        metadata: { age_days: 2, brand: "PM CARES / SBI" }
      },
      {
        id: "evt-03",
        stage: "triage",
        message: "Brand mismatch confirmed: official domain is pmcares.gov.in. Flagged HIGH_RISK.",
        timestamp: "18:10:07",
        level: "error"
      },
      {
        id: "evt-04",
        stage: "detonate",
        message: "Deploying synthetic victim via India Mobile 4G proxy (Android/Chrome).",
        timestamp: "18:10:09",
        level: "info"
      },
      {
        id: "evt-05",
        stage: "detonate",
        message: "Traversing redirect hop: bit.ly/pm-aid -> cdn.redirect-fast.biz -> final scam page.",
        timestamp: "18:10:13",
        level: "warning"
      },
      {
        id: "evt-06",
        stage: "detonate",
        message: "Form autocompleted with synthetic KYC data (dummy name: 'Rohan Sharma').",
        timestamp: "18:10:17",
        level: "info"
      },
      {
        id: "evt-07",
        stage: "detonate",
        message: "PAYMENT SCREEN REACHED. Intercepted dynamic QR and UPI intent handle. Agent halted.",
        timestamp: "18:10:21",
        level: "success"
      },
      {
        id: "evt-08",
        stage: "enrich",
        message: "Decoded UPI VPA: pmcares-relief@okaxis. Resolved PSP: Axis Bank / Google Pay.",
        timestamp: "18:10:23",
        level: "info"
      },
      {
        id: "evt-09",
        stage: "cluster",
        message: "Correlating with campaign graph: VPA links 6 other domains across Maharashtra & NCR.",
        timestamp: "18:10:25",
        level: "warning"
      },
      {
        id: "evt-10",
        stage: "act",
        message: "Cryptographic evidence PDF compiled. Tamper-proof SHA-256 seal generated.",
        timestamp: "18:10:28",
        level: "success"
      }
    ],
    result: {
      case_id: "c-pmcares-9281",
      payee: {
        upi_vpa: "pmcares-relief@okaxis",
        psp_name: "Axis Bank (Google Pay PSP)",
        bank_account: "91802004819201",
        ifsc: "UTIB0000412",
        wallet_address: null
      },
      attribution: "confirmed",
      triage: {
        domain: "pmcares-relief-claim.sbi-update.fake.in",
        domain_age_days: 2,
        registrar: "NameCheap, Inc.",
        claimed_brand: "PM CARES Fund / State Bank of India",
        brand_match: false,
        known_campaign: true,
        should_detonate: true,
        risk_score: 98,
        verdict: "HIGH_RISK",
        reasons: [
          "Domain registered 48 hours ago",
          "Impersonating official government relief scheme",
          "Fast-flux DNS proxy detected on IP 103.21.58.12",
          "Brand mismatch against registered trademark"
        ]
      },
      detonation: {
        target_url: "https://pmcares-relief-claim.sbi-update.fake.in/kyc-verify",
        redirect_chain: [
          "https://bit.ly/pm-aid-2026",
          "https://cdn.redirect-fast.biz/gate?id=9912",
          "https://pmcares-relief-claim.sbi-update.fake.in/kyc-verify",
          "https://pmcares-relief-claim.sbi-update.fake.in/upi-checkout"
        ],
        final_url: "https://pmcares-relief-claim.sbi-update.fake.in/upi-checkout",
        steps: [
          {
            step_number: 1,
            timestamp_offset: "00:01",
            action: "Open initial lure URL",
            target_element: "window.location",
            telemetry: "HTTP 301 Redirect -> cdn.redirect-fast.biz"
          },
          {
            step_number: 2,
            timestamp_offset: "00:04",
            action: "Bypass Bot Detection & CAPTCHA",
            target_element: "div.turnstile-wrapper",
            telemetry: "Synthetic mouse curves generated; device posture passed"
          },
          {
            step_number: 3,
            timestamp_offset: "00:08",
            action: "Fill Fake Aadhaar & Name Form",
            target_element: "input#aadhaar_no, input#full_name",
            dummy_value_used: "Aadhaar: 4129-XXXX-8821 / Name: Rohan Sharma",
            telemetry: "Dummy synthetic profile populated safely"
          },
          {
            step_number: 4,
            timestamp_offset: "00:12",
            action: "Submit Verification Request",
            target_element: "button#verify_now",
            telemetry: "Form submitted; transitioning to payment gateway"
          },
          {
            step_number: 5,
            timestamp_offset: "00:15",
            action: "HALT AT PAYMENT GATEWAY",
            target_element: "div.upi-qr-container",
            telemetry: "Live QR code captured; UPI VPA extracted; zero money spent"
          }
        ],
        extracted_payee: {
          upi_vpa: "pmcares-relief@okaxis",
          psp_name: "Axis Bank",
          bank_account: "91802004819201",
          ifsc: "UTIB0000412"
        },
        qr_payload: "upi://pay?pa=pmcares-relief@okaxis&pn=PM%20Relief%20Fund&am=500.00&cu=INR&tn=Verification%20Fee",
        synthetic_persona: {
          ip_proxy: "49.36.128.44 (Reliance Jio, New Delhi)",
          user_agent: "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 Chrome/128.0.0.0 Mobile Safari/537.36",
          geo: "Delhi, India (IN)",
          device: "Samsung Galaxy S24 Ultra (Emulated)"
        },
        halt_reason: "SAFETY GUARDRAIL: Terminated at payment intercept screen before executing transaction."
      },
      enrichment: {
        resolved_psp: "Axis Bank (Google Pay Merchant Gateway)",
        bank_name: "Axis Bank Limited",
        qr_decoded_uri: "upi://pay?pa=pmcares-relief@okaxis&pn=PM%20Relief%20Fund&am=500.00&cu=INR&tn=Verification%20Fee",
        wallet_chain: null,
        wallet_balance_hint: null
      },
      cluster: {
        cluster_id: "syndicate-pmcares-mule-ring-04",
        size: 7,
        shared_identifiers: [
          "pmcares-relief@okaxis",
          "91802004819201",
          "103.21.58.12",
          "+91-9821049281"
        ]
      },
      evidence_hash: "e4a781b290dfc102a9918734bcfe1239aa81230491823bcda987102938471209",
      drafts: {
        i4c_complaint: `NATIONAL CYBER CRIME REPORTING PORTAL (I4C)
INCIDENT DOSSIER: #STG-2026-9281
Category: Financial Phishing & National Fund Impersonation
Suspect VPA: pmcares-relief@okaxis
Beneficiary Account: 91802004819201 (Axis Bank)
Hosting Infrastructure: 103.21.58.12 (Hostinger ASN 47583)
Lure Domain: pmcares-relief-claim.sbi-update.fake.in
Evidence Integrity SHA-256: e4a781b290dfc102a9918734bcfe1239aa81230491823bcda987102938471209
Compliance: Indian Evidence Act Section 65B Digital Certificate Generated.`,
        bank_alert: {
          target_bank: "Axis Bank Ltd - Nodal Fraud Desk",
          risk_rating: "CRITICAL",
          recommended_action: "IMMEDIATE_LIEN_AND_FREEZE",
          account_number: "91802004819201",
          vpa: "pmcares-relief@okaxis"
        },
        cert_in_advisory: {
          incident_type: "Active Phishing & Malicious UPI Harvesting Campaign",
          malicious_fqdn: "pmcares-relief-claim.sbi-update.fake.in",
          takedown_action: "EMERGENCY_DNS_TAKEDOWN_REQUEST"
        }
      }
    }
  },

  "c-sbikyc-7714": {
    id: "c-sbikyc-7714",
    type: "url",
    target: "https://sbi-card-reward-redeem.online/login",
    status: "completed",
    current_stage: "complete",
    progress_percentage: 100,
    created_at: "2026-10-24T17:45:00Z",
    updated_at: "2026-10-24T17:45:18Z",
    events: [
      {
        id: "evt-201",
        stage: "intake",
        message: "SMS Phishing lure submitted: 'SBI: Your points worth Rs 9850 will expire today. Redeem now: https://sbi-card-reward-redeem.online'.",
        timestamp: "17:45:00",
        level: "info"
      },
      {
        id: "evt-202",
        stage: "triage",
        message: "RDAP check: Domain created 4 days ago. Linked to known mule syndicate: 'syndicate-pmcares-mule-ring-04'.",
        timestamp: "17:45:03",
        level: "warning"
      },
      {
        id: "evt-203",
        stage: "cluster",
        message: "PRE-DETONATION SKIP TRIGGERED: Domain already mapped in campaign graph to VPA 'pmcares-relief@okaxis'. Reusing verified cartel profile.",
        timestamp: "17:45:06",
        level: "success"
      },
      {
        id: "evt-204",
        stage: "act",
        message: "Graph edge attached. Updated impact radius: 8 active scam domains.",
        timestamp: "17:45:10",
        level: "info"
      }
    ],
    result: {
      case_id: "c-sbikyc-7714",
      payee: {
        upi_vpa: "pmcares-relief@okaxis",
        psp_name: "Axis Bank",
        bank_account: "91802004819201",
        ifsc: "UTIB0000412"
      },
      attribution: "confirmed",
      triage: {
        domain: "sbi-card-reward-redeem.online",
        domain_age_days: 4,
        registrar: "Hostinger International",
        claimed_brand: "State Bank of India Card",
        brand_match: false,
        known_campaign: true,
        should_detonate: false,
        risk_score: 95,
        verdict: "HIGH_RISK",
        reasons: [
          "Domain is an exact DNS match to active cartel syndicate",
          "Brand impersonation of State Bank of India",
          "Skip Detonation triggered to preserve API credits"
        ]
      },
      detonation: {
        target_url: "https://sbi-card-reward-redeem.online/login",
        redirect_chain: ["https://sbi-card-reward-redeem.online/login"],
        final_url: "https://sbi-card-reward-redeem.online/login",
        steps: [],
        extracted_payee: {
          upi_vpa: "pmcares-relief@okaxis",
          psp_name: "Axis Bank"
        },
        synthetic_persona: {
          ip_proxy: "Cached Syndication Data",
          user_agent: "System Correlator",
          geo: "IN",
          device: "Virtual Node"
        },
        halt_reason: "Pre-detonation skip: Payee already correlated in graph."
      },
      enrichment: {
        resolved_psp: "Axis Bank",
        bank_name: "Axis Bank Limited"
      },
      cluster: {
        cluster_id: "syndicate-pmcares-mule-ring-04",
        size: 8,
        shared_identifiers: ["pmcares-relief@okaxis", "91802004819201"]
      },
      evidence_hash: "7b8192019cfae902183918401928371629481920384758291029384756192837",
      drafts: {
        i4c_complaint: `SUPPLEMENTARY DOSSIER: Linked to Syndicate #STG-2026-9281`,
        bank_alert: {
          target_bank: "Axis Bank Ltd",
          risk_rating: "CRITICAL",
          recommended_action: "EXPAND_FREEZE_ORDER",
          account_number: "91802004819201",
          vpa: "pmcares-relief@okaxis"
        },
        cert_in_advisory: {
          incident_type: "Cloned Phishing Domain",
          malicious_fqdn: "sbi-card-reward-redeem.online",
          takedown_action: "ADDITIONAL_DOMAIN_TAKEDOWN"
        }
      }
    }
  },

  "c-hdfc-0021": {
    id: "c-hdfc-0021",
    type: "url",
    target: "https://netbanking.hdfcbank.com/netbanking",
    status: "completed",
    current_stage: "complete",
    progress_percentage: 100,
    created_at: "2026-10-24T16:00:00Z",
    updated_at: "2026-10-24T16:00:08Z",
    events: [
      {
        id: "evt-301",
        stage: "intake",
        message: "Candidate URL ingested: https://netbanking.hdfcbank.com/netbanking.",
        timestamp: "16:00:00",
        level: "info"
      },
      {
        id: "evt-302",
        stage: "triage",
        message: "RDAP check: Registered 24 years ago (1999). Registrar: MarkMonitor Inc.",
        timestamp: "16:00:03",
        level: "info"
      },
      {
        id: "evt-303",
        stage: "triage",
        message: "TLS Certificate EV verified to 'HDFC Bank Limited'. Brand match 100%.",
        timestamp: "16:00:05",
        level: "success"
      },
      {
        id: "evt-304",
        stage: "triage",
        message: "DECISION: Legitimate verified banking infrastructure. Detonation aborted.",
        timestamp: "16:00:08",
        level: "success"
      }
    ],
    result: {
      case_id: "c-hdfc-0021",
      payee: {},
      attribution: "benign",
      triage: {
        domain: "netbanking.hdfcbank.com",
        domain_age_days: 9140,
        registrar: "MarkMonitor Inc.",
        claimed_brand: "HDFC Bank",
        brand_match: true,
        known_campaign: false,
        should_detonate: false,
        risk_score: 2,
        verdict: "LOW_RISK",
        reasons: [
          "Domain age > 24 years",
          "Extended Validation SSL matches corporate entity",
          "No redirection anomalies detected"
        ]
      },
      detonation: {
        target_url: "https://netbanking.hdfcbank.com/netbanking",
        redirect_chain: ["https://netbanking.hdfcbank.com/netbanking"],
        final_url: "https://netbanking.hdfcbank.com/netbanking",
        steps: [],
        extracted_payee: {},
        synthetic_persona: {
          ip_proxy: "N/A",
          user_agent: "N/A",
          geo: "IN",
          device: "N/A"
        },
        halt_reason: "Benign target verified. No detonation required."
      },
      enrichment: {
        resolved_psp: "N/A",
        bank_name: "HDFC Bank Limited (Verified)"
      },
      cluster: {
        cluster_id: "none",
        size: 0,
        shared_identifiers: []
      },
      evidence_hash: "0000000000000000000000000000000000000000000000000000000000000000",
      drafts: {
        i4c_complaint: "CASE CLOSED: Target domain is verified authentic banking portal.",
        bank_alert: {
          target_bank: "HDFC Bank",
          risk_rating: "NONE",
          recommended_action: "NO_ACTION",
          account_number: "N/A",
          vpa: "N/A"
        },
        cert_in_advisory: {
          incident_type: "Benign Inspection",
          malicious_fqdn: "netbanking.hdfcbank.com",
          takedown_action: "DISMISS"
        }
      }
    }
  }
};

export const MOCK_GRAPH_DATA: GraphData = {
  nodes: [
    {
      data: {
        id: "vpa-pmcares",
        label: "pmcares-relief@okaxis",
        type: "payee",
        risk_level: "critical",
        metadata: {
          bank: "Axis Bank",
          account: "91802004819201",
          total_revenue_est_inr: 4200000
        }
      }
    },
    {
      data: {
        id: "domain-1",
        label: "pmcares-relief-claim.sbi-update.fake.in",
        type: "domain",
        risk_level: "critical"
      }
    },
    {
      data: {
        id: "domain-2",
        label: "sbi-card-reward-redeem.online",
        type: "domain",
        risk_level: "critical"
      }
    },
    {
      data: {
        id: "domain-3",
        label: "electricity-bill-recovery.biz",
        type: "domain",
        risk_level: "high"
      }
    },
    {
      data: {
        id: "domain-4",
        label: "bijli-bill-urgent-update.in",
        type: "domain",
        risk_level: "high"
      }
    },
    {
      data: {
        id: "domain-5",
        label: "pm-kisan-18th-installment.xyz",
        type: "domain",
        risk_level: "critical"
      }
    },
    {
      data: {
        id: "phone-1",
        label: "+91-9821049281",
        type: "phone",
        risk_level: "high"
      }
    },
    {
      data: {
        id: "ip-1",
        label: "103.21.58.12",
        type: "ip",
        risk_level: "medium"
      }
    },
    {
      data: {
        id: "case-1",
        label: "Case #9281",
        type: "case",
        risk_level: "info"
      }
    },
    {
      data: {
        id: "case-2",
        label: "Case #7714",
        type: "case",
        risk_level: "info"
      }
    }
  ],
  edges: [
    {
      data: {
        id: "e1",
        source: "domain-1",
        target: "vpa-pmcares",
        relationship: "funnel_destination"
      }
    },
    {
      data: {
        id: "e2",
        source: "domain-2",
        target: "vpa-pmcares",
        relationship: "funnel_destination"
      }
    },
    {
      data: {
        id: "e3",
        source: "domain-3",
        target: "vpa-pmcares",
        relationship: "funnel_destination"
      }
    },
    {
      data: {
        id: "e4",
        source: "domain-4",
        target: "vpa-pmcares",
        relationship: "funnel_destination"
      }
    },
    {
      data: {
        id: "e5",
        source: "domain-5",
        target: "vpa-pmcares",
        relationship: "funnel_destination"
      }
    },
    {
      data: {
        id: "e6",
        source: "domain-1",
        target: "ip-1",
        relationship: "dns_host"
      }
    },
    {
      data: {
        id: "e7",
        source: "domain-2",
        target: "ip-1",
        relationship: "dns_host"
      }
    },
    {
      data: {
        id: "e8",
        source: "domain-1",
        target: "phone-1",
        relationship: "shared_mule"
      }
    },
    {
      data: {
        id: "e9",
        source: "case-1",
        target: "domain-1",
        relationship: "investigated_url"
      }
    },
    {
      data: {
        id: "e10",
        source: "case-2",
        target: "domain-2",
        relationship: "investigated_url"
      }
    }
  ],
  total_clusters: 1,
  total_cases_linked: 7,
  disruption_metrics: {
    domains_neutralized: 5,
    estimated_protected_inr: 4200000,
    active_mules_flagged: 1
  }
};
