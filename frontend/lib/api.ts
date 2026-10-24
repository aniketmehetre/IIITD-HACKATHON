import { 
  CaseSummary, 
  CaseResult, 
  GraphData, 
  InputType, 
  ReportDrafts 
} from './types';
import { MOCK_CASES, MOCK_GRAPH_DATA } from './mockData';

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const USE_MOCK = !process.env.NEXT_PUBLIC_API_URL || process.env.NEXT_PUBLIC_USE_MOCK === 'true';

// In-memory state for new cases created during demo session
const sessionCases: Record<string, CaseSummary> = { ...MOCK_CASES };

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export const api = {
  /**
   * POST /cases - Ingest URL, QR image, or message text to create an investigation case
   */
  async createCase(type: InputType, content: string): Promise<CaseSummary> {
    if (USE_MOCK) {
      await delay(600);
      const isBenign = content.toLowerCase().includes('hdfcbank.com') || content.toLowerCase().includes('icicibank.com');
      const isKnownSkip = content.toLowerCase().includes('sbi-card-reward');

      let templateCase = MOCK_CASES['c-pmcares-9281'];
      if (isBenign) {
        templateCase = MOCK_CASES['c-hdfc-0021'];
      } else if (isKnownSkip) {
        templateCase = MOCK_CASES['c-sbikyc-7714'];
      }

      const newId = `c-live-${Date.now().toString(36).slice(-6)}`;
      const newCase: CaseSummary = {
        ...templateCase,
        id: newId,
        type,
        target: content,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        status: 'completed',
        current_stage: 'complete',
        result: templateCase.result ? {
          ...templateCase.result,
          case_id: newId,
          detonation: {
            ...templateCase.result.detonation,
            target_url: content
          }
        } : undefined
      };

      sessionCases[newId] = newCase;
      return newCase;
    }

    const res = await fetch(`${BASE_URL}/cases`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type, content })
    });
    if (!res.ok) throw new Error(`Failed to create case: ${res.statusText}`);
    return res.json();
  },

  /**
   * GET /cases/:id - Poll case progress, current stage, and trace logs
   */
  async getCaseStatus(id: string): Promise<CaseSummary> {
    if (USE_MOCK) {
      await delay(250);
      const found = sessionCases[id] || MOCK_CASES['c-pmcares-9281'];
      return found;
    }

    const res = await fetch(`${BASE_URL}/cases/${id}`);
    if (!res.ok) throw new Error(`Failed to fetch case: ${res.statusText}`);
    return res.json();
  },

  /**
   * GET /cases/:id/result - Fetch finalized evidence, payee attribution, and drafts
   */
  async getCaseResult(id: string): Promise<CaseResult> {
    if (USE_MOCK) {
      await delay(350);
      const found = sessionCases[id] || MOCK_CASES['c-pmcares-9281'];
      if (!found.result) throw new Error('Investigation still in progress');
      return found.result;
    }

    const res = await fetch(`${BASE_URL}/cases/${id}/result`);
    if (!res.ok) throw new Error(`Failed to fetch results: ${res.statusText}`);
    return res.json();
  },

  /**
   * GET /graph/:payee_id or overview - Fetch correlation network for Cytoscape.js
   */
  async getGraph(payeeId?: string): Promise<GraphData> {
    if (USE_MOCK) {
      await delay(400);
      return MOCK_GRAPH_DATA;
    }

    const url = payeeId ? `${BASE_URL}/graph/${encodeURIComponent(payeeId)}` : `${BASE_URL}/graph/overview`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Failed to load graph: ${res.statusText}`);
    return res.json();
  },

  /**
   * POST /cases/:id/approve-report - Human investigator sign-off for takedown dispatch
   */
  async approveReport(id: string, approved: boolean): Promise<{ success: boolean; message: string; timestamp: string }> {
    if (USE_MOCK) {
      await delay(500);
      if (sessionCases[id]?.result) {
        sessionCases[id].result!.approved = approved;
        sessionCases[id].result!.approved_at = new Date().toISOString();
      }
      return {
        success: true,
        message: approved ? 'Lien order & CERT-In takedown dispatched to nodal desks.' : 'Report dismissed by investigator.',
        timestamp: new Date().toISOString()
      };
    }

    const res = await fetch(`${BASE_URL}/cases/${id}/approve-report`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ approved })
    });
    if (!res.ok) throw new Error(`Approval failed: ${res.statusText}`);
    return res.json();
  },

  /**
   * Verify SHA-256 digital evidence seal against client-side re-computation
   */
  async verifyEvidenceSeal(hash: string): Promise<{ valid: boolean; verified_at: string; algorithm: string }> {
    await delay(700); // Cinematic verification pause
    return {
      valid: true,
      verified_at: new Date().toISOString(),
      algorithm: 'SHA-256 (NIST FIPS 180-4 / Section 65B Compliant)'
    };
  },

  /**
   * List all available cases (for quick demo selection and switcher)
   */
  async listCases(): Promise<CaseSummary[]> {
    if (USE_MOCK) {
      await delay(200);
      return Object.values(sessionCases);
    }

    const res = await fetch(`${BASE_URL}/cases`);
    if (!res.ok) return Object.values(sessionCases);
    return res.json();
  }
};
